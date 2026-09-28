#!/bin/bash

if [ "$#" -lt "1" ] 
then 
    echo 
    echo $0: Error: path argument is missing! Abort!
    echo
    exit 1
fi

echo $0: generate compilation time string and SHA256 message digest

VERFILE="$1/"version.hppgen

printf "" > "$VERFILE"

#TIME=`env TZ=Europe/Berlin date +"%a, %b %d %Y, %H:%M:%S"`
TIME=`date +"%Y-%m-%d %H:%M:%S"`

#sort files
L=`ls "$1/"*.cpp "$1/"*.hpp | sort`
# choose a sha256 utility that's available on the system
if command -v sha256sum >/dev/null 2>&1; then
        SHA_CMD="sha256sum"
elif command -v shasum >/dev/null 2>&1; then
        SHA_CMD="shasum -a 256"
else
        echo "$0: Error: neither sha256sum nor shasum is available. Install coreutils or use shasum."
        exit 1
fi

# compute per-file checksums and write to temporary key file
${SHA_CMD} $L > "$1/key"


file="$1/key"
fileout="$1/key2"
rm -f $fileout

#this removes the local paths to each src file
while IFS= read -r line
do
	#printf '%s\n' "$line"

        S=`echo $line | awk '{ print $1 }' `
        F=`echo $line | awk '{ print $2 }' `
 
        RP=${F##*/}
        echo $S " "$RP >> $fileout


done <"$file"



# compute overall checksum of the aggregated (basename) list
S2=`${SHA_CMD} "$fileout"`

#S2=${S2%" key"}

S2=${S2%% *}

#rm "$1/"key

printf '#include<string>\n' >> "$VERFILE"

printf '\n' >> "$VERFILE"

printf 'const std::string GLOBAL_COMPILATION_TIME = "%s";\n' "$TIME" >> "$VERFILE"

printf 'const std::string GLOBAL_SHA256 = "%s";\n' "$S2" >> "$VERFILE"

# write detailed sha256 values in a portable way
printf 'const std::string GLOBAL_SHA256_DETAILED = "' >> "$VERFILE"
while IFS= read -r line
do
        # append each line followed by a literal "\n"
        printf '%s\\n' "$line" >> "$VERFILE"
done <"$fileout"

printf '";\n' >> "$VERFILE"

