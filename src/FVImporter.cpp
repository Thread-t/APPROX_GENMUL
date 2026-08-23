#include "FVImporter.hpp"
#include "ApproxConfig.hpp"

#include <fstream>
#include <sstream>
#include <regex>
#include <cctype>

// Simple boolean expression evaluator for expressions using X,Y,Z,0,1 and operators ~ & | ^ and parentheses
namespace {
    // tokenize
    struct Token { string s; };

    vector<string> tokenizeExpr(const string &expr)
    {
        vector<string> out;
        string tok;
        for (size_t i=0;i<expr.size();++i)
        {
            char c = expr[i];
            if (isspace((unsigned char)c)) continue;
            if (c=='('||c==')'||c=='~'||c=='&'||c=='|'||c=='^') {
                if (!tok.empty()) { out.push_back(tok); tok.clear(); }
                string s(1,c); out.push_back(s); continue;
            }
            // identifier or number
            if (isalnum((unsigned char)c) || c=='_' || c=='\'') {
                tok.push_back(c);
            } else {
                if (!tok.empty()) { out.push_back(tok); tok.clear(); }
                string s(1,c); out.push_back(s);
            }
        }
        if (!tok.empty()) out.push_back(tok);
        return out;
    }

    int prec(const string &op)
    {
        if (op=="~") return 4;
        if (op=="&") return 3;
        if (op=="^") return 2;
        if (op=="|") return 1;
        return 0;
    }

    vector<string> toRPN(const string &expr)
    {
        auto toks = tokenizeExpr(expr);
        vector<string> out;
        vector<string> st;
        for (auto &t : toks)
        {
            if (t=="X"||t=="Y"||t=="Z"||t=="0"||t=="1") { out.push_back(t); }
            else if (t=="~") { st.push_back(t); }
            else if (t=="(") { st.push_back(t); }
            else if (t==")") {
                while(!st.empty() && st.back()!="(") { out.push_back(st.back()); st.pop_back(); }
                if (!st.empty() && st.back()=="(") st.pop_back();
            }
            else if (t=="&"||t=="|"||t=="^") {
                while(!st.empty() && prec(st.back())>=prec(t)) { out.push_back(st.back()); st.pop_back(); }
                st.push_back(t);
            }
            else {
                // ignore unknown tokens like | or extra text
                // try to handle multi-char tokens like 1'b0 -> extract 0 or 1
                if (t.find("1'b0")!=string::npos || t=="0") out.push_back("0");
                else if (t.find("1'b1")!=string::npos || t=="1") out.push_back("1");
            }
        }
        while(!st.empty()) { out.push_back(st.back()); st.pop_back(); }
        return out;
    }

    int evalRPN(const vector<string> &rpn, int xv, int yv, int zv)
    {
        vector<int> st;
        for (auto &t : rpn)
        {
            if (t=="X") st.push_back(xv);
            else if (t=="Y") st.push_back(yv);
            else if (t=="Z") st.push_back(zv);
            else if (t=="0") st.push_back(0);
            else if (t=="1") st.push_back(1);
            else if (t=="~") {
                if (st.empty()) return 0;
                int a = st.back(); st.pop_back(); st.push_back(!a);
            }
            else if (t=="&") { int b=st.back(); st.pop_back(); int a=st.back(); st.pop_back(); st.push_back(a & b); }
            else if (t=="^") { int b=st.back(); st.pop_back(); int a=st.back(); st.pop_back(); st.push_back(a ^ b); }
            else if (t=="|") { int b=st.back(); st.pop_back(); int a=st.back(); st.pop_back(); st.push_back(a | b); }
            else {
                // numeric fallback
                if (!t.empty() && isdigit((unsigned char)t[0])) st.push_back(t[0]-'0');
            }
        }
        if (st.empty()) return 0;
        return st.back();
    }
}

bool importFVPreset(const string &filePath)
{
    ifstream ifs(filePath);
    if (!ifs) return false;
    string content((istreambuf_iterator<char>(ifs)), istreambuf_iterator<char>());

    // find all approx module definitions
    regex modRegex(R"(module\s+(approx_fa_[A-Za-z0-9_]+)\s*\(\s*X\s*,\s*Y\s*,\s*Z\s*,\s*S\s*,\s*Cout\s*\)\s*;)");
    smatch m;
    string s = content;
    auto searchStart = s.cbegin();
    while (regex_search(searchStart, s.cend(), m, modRegex))
    {
        string modName = m[1];
        // extract until endmodule
        auto pos = m.position(0) + (searchStart - s.cbegin());
        size_t start = pos;
        size_t end = s.find("endmodule", start);
        if (end==string::npos) break;
        string body = s.substr(start, end - start);

        // find assign lines for Cout and S
        regex assignRegex(R"(assign\s+(Cout|S)\s*=\s*([^;]+);)");
        smatch am;
        string exprC="", exprS="";
        string::const_iterator bs = body.cbegin();
        while (regex_search(bs, body.cend(), am, assignRegex))
        {
            string lhs = am[1]; string rhs = am[2];
            if (lhs=="Cout") exprC = rhs;
            else if (lhs=="S") exprS = rhs;
            bs = am.suffix().first;
        }

        if (exprC.empty() || exprS.empty()) { searchStart = m.suffix().first; continue; }

        auto rpnC = toRPN(exprC);
        auto rpnS = toRPN(exprS);
        vector<int> truth(8,0);
        for (int x=0;x<2;++x) for (int y=0;y<2;++y) for (int z=0;z<2;++z)
        {
            int idx = (x<<2)|(y<<1)|z;
            int c = evalRPN(rpnC, x,y,z);
            int ss = evalRPN(rpnS, x,y,z);
            truth[idx] = ((c&1)<<1) | (ss&1);
        }

        // find instantiations of this module inside DT module
        // find DT module body
        regex dtRegex(R"(module\s+DT\s*\([^;]+;)");
        smatch dm;
        if (regex_search(s, dm, dtRegex)) {
            // get DT module start position
            size_t dtPos = dm.position(0);
            size_t dtEnd = s.find("endmodule", dtPos);
            if (dtEnd!=string::npos) {
                string dtBody = s.substr(dtPos, dtEnd-dtPos);
                // find lines with this module name
                regex instRegex(modName + R"(\s+[A-Za-z0-9_]+\s*\(([^;]+)\);)");
                smatch im;
                string::const_iterator is = dtBody.cbegin();
                while (regex_search(is, dtBody.cend(), im, instRegex))
                {
                    string args = im[1];
                    // find INk occurrences
                    regex inRegex(R"(IN(\d+)\s*\[)");
                    smatch inM;
                    string::const_iterator as = args.cbegin();
                    while (regex_search(as, args.cend(), inM, inRegex))
                    {
                        int weight = stoi(inM[1]);
                        ApproxConfig::setApproxForWeight(weight, truth);
                        as = inM.suffix().first;
                    }
                    is = im.suffix().first;
                }
            }
        }

        searchStart = m.suffix().first;
    }

    return true;
}
