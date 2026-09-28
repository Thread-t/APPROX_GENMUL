#!/usr/bin/env python3
"""Approx GenMul — desktop front-end for the GenMul RTL generator.

Designer tab builds the command line for the `genmul` binary, Output shows
the raw generation/equivalence-check log, and Tree Preview renders the exact
same partial-product reduction diagram as the static PNG preview and the
interactive HTML tree (tree_viewer.py is the single source of truth for the
column/stage layout math; this file only turns it into Tkinter canvas items).
"""
import subprocess
import webbrowser
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
except ImportError:
    raise SystemExit('Tkinter is required for the GUI shell. Please install tkinter for your Python build.')

try:
    from tree_viewer import (
        parse_verilog_tree,
        generate_tree_html,
        DOT_R, DOT_GAP, COL_GAP, GROUP_GAP,
        DOT_COLOR, EXACT_COLOR, APPROX_COLOR,
        _ordered_blocks,
    )
    TREE_VIEWER_AVAILABLE = True
except Exception:
    TREE_VIEWER_AVAILABLE = False


APP_NAME = 'Approx GenMul'
APP_VERSION = '2.0'

ROOT = Path(__file__).resolve().parent.parent
BINARY = ROOT / 'build' / 'bin' / 'genmul'
if not BINARY.exists():
    BINARY = ROOT / 'build' / 'src' / 'genmul'

ICON_PNG = ROOT / 'genmul_icon.png'
ICON_JPG = ROOT / 'Genmul_Logo.jpg'


def ensure_icon_file():
    # Prefer a high-quality PNG icon, but refresh it from the source JPG if needed.
    if ICON_JPG.exists():
        try:
            from PIL import Image
            img = Image.open(ICON_JPG).convert('RGBA')
            max_size = (1500, 900)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            img.save(ICON_PNG, format='PNG', optimize=True)
            return str(ICON_PNG)
        except Exception:
            pass

    if ICON_PNG.exists():
        return str(ICON_PNG)

    return str(ICON_JPG) if ICON_JPG.exists() else str(ICON_PNG)


# ----------------------------------------------------------------------
# Theme
# ----------------------------------------------------------------------
THEME = {
    'app_bg':      '#eef2f8',
    'panel_bg':    '#ffffff',
    'header_bg':   '#0f2a4a',
    'header_fg':   '#ffffff',
    'header_sub':  '#b9cbe6',
    'border':      '#d8e0ec',
    'text':        '#13233a',
    'muted':       '#64748b',
    'primary':     '#155fbf',
    'primary_dk':  '#0d4a94',
    'secondary':   '#e6eefb',
    'secondary_fg':'#0d4a94',
    'success':     '#1f9d55',
    'success_dk':  '#177a42',
    'danger':      '#c0392b',
    'approx':      '#d9534f',
    'exact':       '#2f9e44',
    'console_bg':  '#0f172a',
    'console_fg':  '#d7e2f2',
    'status_bg':   '#0f2a4a',
    'status_fg':   '#dce7f7',
}

FONT_FAMILY = 'Segoe UI'

PPG_OPTIONS = [('Unsigned', '1'), ('Signed', '2')]
PPA_OPTIONS = [
    ('Array', '1'), ('Wallace', '2'), ('Dadda', '3'), ('Counter-Wallace', '4'),
    ('Approximate Dadda', '5'), ('Approximate Array', '6'), ('Approximate Wallace', '7')
]
FSA_OPTIONS = [
    ('Ripple Carry', '1'), ('Carry Look-Ahead', '2'), ('Lander-Fischer', '3'), ('Kogge-Stone', '4'),
    ('Brent-Kung', '5'), ('Carry Skip', '6'), ('Serial Prefix', '7')
]
METHOD_OPTIONS = [('Exact', '0'), ('Truncation', '1'), ('FA substitute', '2'), ('Both', '3')]
DEBUG_OPTIONS = [('Off', '0'), ('On', '1')]

FIELD_HELP = {
    'ppg': 'How partial products are generated from the two operands.',
    'ppa': 'Partial-product array / reduction scheme used to compress the rows.',
    'fsa': 'Final-stage adder that combines the fully reduced sum and carry rows.',
    'in1': 'Bit width of the first operand (multiplicand).',
    'in2': 'Bit width of the second operand (multiplier).',
    'col': 'Column index from which approximation starts being applied.',
    'cout': 'Bitmask selecting which carry-output adders are approximated.',
    'sum': 'Bitmask selecting which sum-output adders are approximated.',
    'method': 'Technique used to approximate the selected reduction cells.',
    'debug': 'Verbose RTL generation for debugging; skips the tree preview.',
}


class GenMulApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f'{APP_NAME}')
        self.root.geometry('1040x720')
        self.root.minsize(920, 620)
        self.root.configure(bg=THEME['app_bg'])

        icon_file = ensure_icon_file()
        self._icon_photo = None
        if icon_file and Path(icon_file).exists():
            try:
                try:
                    photo = tk.PhotoImage(file=icon_file)
                except Exception:
                    from PIL import Image, ImageTk
                    img = Image.open(icon_file)
                    photo = ImageTk.PhotoImage(img)
                self._icon_photo = photo
                self.root.iconphoto(True, self._icon_photo)
            except Exception:
                pass

        self._build_style()
        self._build_menu()

        # Overall shell: header banner, tabbed body, status bar.
        self._build_header()

        self.notebook = ttk.Notebook(self.root, style='App.TNotebook')
        self.notebook.pack(fill='both', expand=True, padx=14, pady=(4, 0))

        self.config_frame = ttk.Frame(self.notebook, style='Panel.TFrame')
        self.results_frame = ttk.Frame(self.notebook, style='Panel.TFrame')
        self.tree_frame = ttk.Frame(self.notebook, style='Panel.TFrame')
        self.notebook.add(self.config_frame, text='  Designer  ')
        self.notebook.add(self.results_frame, text='  Output  ')
        self.notebook.add(self.tree_frame, text='  Tree Preview  ')

        self._build_status_bar()

        self.build_form()
        self.build_output_panel()
        self.build_tree_panel()

        self.set_status('Ready.')

    # ------------------------------------------------------------------
    # Styling / chrome
    # ------------------------------------------------------------------
    def _build_style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use('clam')
        except Exception:
            pass

        style.configure('.', font=(FONT_FAMILY, 10))

        style.configure('Panel.TFrame', background=THEME['panel_bg'])
        style.configure('App.TFrame', background=THEME['app_bg'])
        style.configure('TFrame', background=THEME['panel_bg'])
        style.configure('TLabel', background=THEME['panel_bg'], foreground=THEME['text'])
        style.configure('Muted.TLabel', background=THEME['panel_bg'], foreground=THEME['muted'],
                         font=(FONT_FAMILY, 9))
        style.configure('SectionTitle.TLabel', background=THEME['panel_bg'], foreground=THEME['text'],
                         font=(FONT_FAMILY, 11, 'bold'))

        style.configure('App.TNotebook', background=THEME['app_bg'], borderwidth=0)
        style.configure('App.TNotebook.Tab', font=(FONT_FAMILY, 10, 'bold'),
                         padding=(14, 8), background=THEME['secondary'], foreground=THEME['secondary_fg'])
        style.map('App.TNotebook.Tab',
                  background=[('selected', THEME['panel_bg'])],
                  foreground=[('selected', THEME['primary_dk'])])

        style.configure('Section.TLabelframe', background=THEME['panel_bg'], borderwidth=1,
                         relief='solid', bordercolor=THEME['border'])
        style.configure('Section.TLabelframe.Label', background=THEME['panel_bg'],
                         foreground=THEME['primary_dk'], font=(FONT_FAMILY, 10, 'bold'))

        style.configure('TCombobox', padding=4)
        style.configure('TEntry', padding=4)

        style.configure('Primary.TButton', background=THEME['primary'], foreground='white',
                         font=(FONT_FAMILY, 10, 'bold'), padding=(12, 7), borderwidth=0)
        style.map('Primary.TButton', background=[('active', THEME['primary_dk']), ('disabled', '#9fb7d8')])

        style.configure('Secondary.TButton', background=THEME['secondary'], foreground=THEME['secondary_fg'],
                         font=(FONT_FAMILY, 10, 'bold'), padding=(12, 7), borderwidth=0)
        style.map('Secondary.TButton', background=[('active', '#d5e3f8'), ('disabled', '#eef2f8')])

        style.configure('Success.TButton', background=THEME['success'], foreground='white',
                         font=(FONT_FAMILY, 10, 'bold'), padding=(12, 7), borderwidth=0)
        style.map('Success.TButton', background=[('active', THEME['success_dk']), ('disabled', '#a9d9bd')])

        style.configure('Tool.TButton', background=THEME['panel_bg'], foreground=THEME['text'],
                         font=(FONT_FAMILY, 9, 'bold'), padding=(8, 4), borderwidth=1, relief='solid')
        style.map('Tool.TButton', background=[('active', THEME['secondary'])])

        style.configure('Horizontal.TScale', background=THEME['panel_bg'])
        style.configure('TScrollbar', background=THEME['secondary'])

    def _build_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label='Open Tree HTML', command=self.open_tree_view)
        file_menu.add_separator()
        file_menu.add_command(label='Exit', command=self.root.quit)
        menubar.add_cascade(label='File', menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label='Reset Tree View', command=lambda: self._reset_tree_zoom())
        menubar.add_cascade(label='View', menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label='About', command=self._show_about)
        menubar.add_cascade(label='Help', menu=help_menu)

        self.root.config(menu=menubar)

    def _show_about(self):
        messagebox.showinfo(
            f'About {APP_NAME}',
            f'{APP_NAME}  v{APP_VERSION}\n\n'
            'A desktop front-end for generating exact and approximate '
            'multiplier RTL, and for inspecting the resulting partial-product '
            'reduction tree.'
        )

    def _build_header(self):
        #sayak: Header image adjustment 
        header = tk.Frame(self.root, bg=THEME['header_bg'], height=96)
        header.pack(fill='x', side='top')
        header.pack_propagate(False)

        logo_label = None
        try:
            icon_path = ensure_icon_file()
            if icon_path and Path(icon_path).exists():
                from PIL import Image, ImageTk
                img = Image.open(icon_path).convert('RGBA')
                # Sayak: Image Thumbnail increase
                img.thumbnail((132, 132), Image.Resampling.LANCZOS)
                self._header_logo = ImageTk.PhotoImage(img)
                logo_label = tk.Label(header, image=self._header_logo, bg=THEME['header_bg'],
                                       borderwidth=0, highlightthickness=0)
        except Exception:
            logo_label = None

        if logo_label:
            logo_label.pack(side='left', padx=(18, 14), pady=10)

        text_frame = tk.Frame(header, bg=THEME['header_bg'])
        text_frame.pack(side='left', pady=18)
        tk.Label(text_frame, text=APP_NAME, bg=THEME['header_bg'], fg=THEME['header_fg'],
                 font=(FONT_FAMILY, 18, 'bold')).pack(anchor='w')
        tk.Label(text_frame, text='Exact & approximate multiplier RTL generator',
                 bg=THEME['header_bg'], fg=THEME['header_sub'],
                 font=(FONT_FAMILY, 9)).pack(anchor='w')

        tk.Label(header, text=f'v{APP_VERSION}', bg=THEME['header_bg'], fg=THEME['header_sub'],
                 font=(FONT_FAMILY, 9)).pack(side='right', padx=18)

    def _build_status_bar(self):
        bar = tk.Frame(self.root, bg=THEME['status_bg'], height=26)
        bar.pack(fill='x', side='bottom')
        bar.pack_propagate(False)
        self.status_var = tk.StringVar(value='Ready.')
        tk.Label(bar, textvariable=self.status_var, bg=THEME['status_bg'], fg=THEME['status_fg'],
                 font=(FONT_FAMILY, 9), anchor='w').pack(side='left', padx=12)

    def set_status(self, text):
        self.status_var.set(text)
        self.root.update_idletasks()

    # ------------------------------------------------------------------
    # Sayak: Adjustment of the main frame slider
    # ------------------------------------------------------------------
    def build_form(self):
        canvas = tk.Canvas(self.config_frame, bg=THEME['app_bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.config_frame, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side='left', fill='both', expand=True, padx=(18, 0), pady=16)
        scrollbar.pack(side='right', fill='y', pady=16)

        inner = ttk.Frame(canvas, style='Panel.TFrame')
        inner_id = canvas.create_window((0, 0), window=inner, anchor='nw')

        def _fit_form_width():
            available = max(640, self.config_frame.winfo_width() - 56)
            target = min(980, available)
            canvas.itemconfigure(inner_id, width=target)
            canvas.configure(scrollregion=canvas.bbox('all'))

        _fit_form_width()
        canvas.bind('<Configure>', lambda event: _fit_form_width())
        inner.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))

        self.values = {}
        self.option_maps = {}
        self.approx_controls = []
        self.field_rows = {}

        core_frame = ttk.Labelframe(inner, text=' Multiplier Configuration ', style='Section.TLabelframe')
        core_frame.pack(fill='x', pady=(0, 12))
        core_fields = [
            ('PPG (Partial Product Gen.)', 'ppg', ttk.Combobox, PPG_OPTIONS, 'Unsigned'),
            ('PPA (Reduction Scheme)', 'ppa', ttk.Combobox, PPA_OPTIONS, 'Array'),
            ('FSA (Final Stage Adder)', 'fsa', ttk.Combobox, FSA_OPTIONS, 'Ripple Carry'),
            ('Input 1 bit width', 'in1', ttk.Entry, None, '8'),
            ('Input 2 bit width', 'in2', ttk.Entry, None, '8'),
        ]
        self._build_fields(core_frame, core_fields)

        approx_frame = ttk.Labelframe(inner, text=' Approximation Parameters ', style='Section.TLabelframe')
        approx_frame.pack(fill='x', pady=(0, 12))
        approx_fields = [
            ('Approx. column', 'col', ttk.Entry, None, '2'),
            ('Carry mask', 'cout', ttk.Entry, None, '23'),
            ('Sum mask', 'sum', ttk.Entry, None, '105'),
            ('Approx. method', 'method', ttk.Combobox, METHOD_OPTIONS, 'FA substitute'),
            ('Debug mode', 'debug', ttk.Combobox, DEBUG_OPTIONS, 'Off'),
        ]
        self._build_fields(approx_frame, approx_fields)
        for key in ('col', 'cout', 'sum', 'method', 'debug'):
            self.approx_controls.append(self.values[key])

        self.values['ppa'].bind('<<ComboboxSelected>>', lambda event: self._update_approx_controls())
        self._update_approx_controls()

        action_row = ttk.Frame(inner, style='Panel.TFrame')
        action_row.pack(fill='x', pady=(6, 0))
        ttk.Button(action_row, text='▶  Generate RTL', style='Primary.TButton',
                   command=self.generate_design).pack(side='left', padx=(0, 8))
        ttk.Button(action_row, text='🔄  Run Full Flow', style='Primary.TButton',
                   command=self.run_full_flow).pack(side='left', padx=(0, 8))
        ttk.Button(action_row, text='🌳  Open Tree HTML', style='Secondary.TButton',
                   command=self.open_tree_view).pack(side='left', padx=(0, 8))
        ttk.Button(action_row, text='⬇  Export Tree HTML', style='Secondary.TButton',
                   command=self.export_tree_html).pack(side='left')

    def _build_fields(self, parent, fields):
        body = ttk.Frame(parent, style='Panel.TFrame')
        body.pack(fill='x', padx=14, pady=(10, 12))
        body.columnconfigure(1, weight=1)

        for row_idx, (label_text, key, widget_type, options, default) in enumerate(fields):
            ttk.Label(body, text=label_text, width=24, anchor='w',
                      font=(FONT_FAMILY, 10, 'bold')).grid(row=row_idx * 2, column=0, sticky='w', pady=(6, 0))

            if widget_type is ttk.Entry:
                widget = ttk.Entry(body, width=28)
                widget.insert(0, default)
            else:
                widget = ttk.Combobox(body, state='readonly', width=26)
                labels = [label for label, _ in options]
                widget['values'] = labels
                widget.set(default)
                self.option_maps[key] = {label: value for label, value in options}

            widget.grid(row=row_idx * 2, column=1, sticky='ew', padx=(10, 0), pady=(6, 0))
            self.values[key] = widget
            self.field_rows[key] = widget

            help_text = FIELD_HELP.get(key, '')
            if help_text:
                ttk.Label(body, text=help_text, style='Muted.TLabel', wraplength=520,
                          justify='left').grid(row=row_idx * 2 + 1, column=1, sticky='w', padx=(10, 0), pady=(0, 4))

    # Sayak: bind with the equivalence check script
    def run_equiv_check(self):
        script = ROOT / 'src' / 'run_equiv_check.sh'
        if not script.exists():
            messagebox.showerror('Missing script', f'Could not find the equivalence script at: {script}')
            return

        self.output_text.delete('1.0', 'end')
        self.output_text.insert('end', f'Running equivalence check: {script}\n\n')
        self.notebook.select(self.results_frame)
        self.set_status('Running equivalence check…')

        try:
            proc = subprocess.run([str(script)], cwd=str(ROOT / 'src'), check=False,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            out = proc.stdout
        except Exception as exc:
            out = f'Failed to run script: {exc}'

        self.output_text.insert('end', out)
        self.set_status('Equivalence check finished.')
        messagebox.showinfo('Equivalence check finished', 'Equivalence check completed — see Output tab for details.')

    def run_full_flow(self):
        """Generates the approximate RTL, builds the exact golden model, and runs Yosys CEC."""
        script = ROOT / 'src' / 'run_flow.sh'
        if not script.exists():
            messagebox.showerror('Missing Script', f'Could not find execution script at:\n{script}')
            return

        if not BINARY.exists():
            messagebox.showerror('Missing Binary', f'Could not find genmul binary at:\n{BINARY}')
            return

        try:
            ppg = self._combo_value('ppg')
            ppa = self._combo_value('ppa')
            fsa = self._combo_value('fsa')
            in1 = self._read_value('in1', 'int')
            in2 = self._read_value('in2', 'int')
            col = self._read_value('col', 'int')
            cout = self._read_value('cout', 'int')
            sum_mask = self._read_value('sum', 'int')
            method = self._combo_value('method')
            debug = 1
        except ValueError as err:
            messagebox.showerror('Invalid Input', str(err))
            return

        if int(ppa) not in {5, 6, 7}:
            messagebox.showwarning(
                'Approximate flow only',
                'The full verification flow is intended for approximate reduction modes only. '
                'Please select Approximate Dadda, Approximate Array, or Approximate Wallace.'
            )
            return

        out_dir = ROOT / 'build' / 'output'
        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(script),
            str(BINARY),
            str(out_dir),
            str(ppg), str(ppa), str(fsa),
            str(in1), str(in2),
            str(col), str(cout), str(sum_mask),
            str(method), str(debug),
        ]

        self.output_text.delete('1.0', 'end')
        self.output_text.insert('end', f'Triggering full flow:\n{" ".join(cmd)}\n\n')
        self.notebook.select(self.results_frame)
        self.set_status('Running generation and equivalence check…')

        def execute():
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                if proc.stdout is None:
                    self.output_text.insert('end', 'No process output captured.\n')
                    self.set_status('Flow execution failed.')
                    return

                for line in proc.stdout:
                    self.output_text.insert('end', line)
                    self.output_text.see('end')
                    self.root.update_idletasks()

                returncode = proc.wait()
                if returncode == 0:
                    self.set_status('Flow completed successfully.')
                    messagebox.showinfo('Success', 'Generation and equivalence check completed successfully!')
                else:
                    self.set_status('Flow finished with errors or mismatch.')
                    messagebox.showwarning('Flow finished', 'The process completed with a non-zero exit code. See the Output tab for details.')
            except Exception as exc:
                self.output_text.insert('end', f'\nExecution error: {exc}\n')
                self.set_status('Execution failed.')
                messagebox.showerror('Execution failed', str(exc))

        self.root.after(100, execute)

    # ------------------------------------------------------------------
    # Output tab
    # ------------------------------------------------------------------
    def build_output_panel(self):
        wrapper = ttk.Frame(self.results_frame, style='Panel.TFrame')
        wrapper.pack(fill='both', expand=True, padx=18, pady=16)

        toolbar = ttk.Frame(wrapper, style='Panel.TFrame')
        toolbar.pack(fill='x', pady=(0, 8))
        ttk.Label(toolbar, text='Generation Log', style='SectionTitle.TLabel').pack(side='left')
        ttk.Button(toolbar, text='Clear', style='Tool.TButton',
                   command=lambda: self.output_text.delete('1.0', 'end')).pack(side='right')

        console_frame = tk.Frame(wrapper, bg=THEME['console_bg'], bd=0)
        console_frame.pack(fill='both', expand=True)
        self.output_text = tk.Text(console_frame, wrap='word', bg=THEME['console_bg'], fg=THEME['console_fg'],
                                    insertbackground=THEME['console_fg'], font=('Consolas', 10),
                                    relief='flat', padx=12, pady=10)
        self.output_text.pack(fill='both', expand=True)
        self.output_text.insert('end', 'Generate a design to inspect the produced Verilog and the tree metadata for the selected multiplier.')

    # ------------------------------------------------------------------
    # Sayak: Tree Preview tab
    # ------------------------------------------------------------------
    def build_tree_panel(self):
        self.tree_zoom = 1.0
        self.current_graph = None
        self.tree_photo = None
        self.node_lookup = {}

        wrapper = ttk.Frame(self.tree_frame, style='Panel.TFrame')
        wrapper.pack(fill='both', expand=True, padx=18, pady=16)

        # Legend + toolbar row.
        toolbar = ttk.Frame(wrapper, style='Panel.TFrame')
        toolbar.pack(fill='x', pady=(0, 8))

        legend = ttk.Frame(toolbar, style='Panel.TFrame')
        legend.pack(side='left')
        self._legend_swatch(legend, DOT_COLOR if TREE_VIEWER_AVAILABLE else '#1a8525', 'Partial product bit')
        self._legend_swatch(legend, EXACT_COLOR if TREE_VIEWER_AVAILABLE else '#8fa39e', 'Exact adder')
        self._legend_swatch(legend, APPROX_COLOR if TREE_VIEWER_AVAILABLE else '#eaa1a1', 'Approximate adder')

        zoom_controls = ttk.Frame(toolbar, style='Panel.TFrame')
        zoom_controls.pack(side='right')
        ttk.Button(zoom_controls, text='−', width=3, style='Tool.TButton',
                   command=lambda: self._set_tree_zoom(1 / 1.2)).pack(side='left', padx=2)
        ttk.Button(zoom_controls, text='+', width=3, style='Tool.TButton',
                   command=lambda: self._set_tree_zoom(1.2)).pack(side='left', padx=2)
        ttk.Button(zoom_controls, text='Reset', style='Tool.TButton',
                   command=self._reset_tree_zoom).pack(side='left', padx=(2, 10))
        self.tree_zoom_var = tk.DoubleVar(value=1.0)
        zoom_scale = ttk.Scale(zoom_controls, from_=0.3, to=3.0, orient='horizontal',
                               variable=self.tree_zoom_var, command=self._on_zoom_slider, length=140)
        zoom_scale.pack(side='left')

        ttk.Button(zoom_controls, text='Generate Dadda PNG', style='Secondary.TButton',
                   command=self._generate_dadda_tree_image).pack(side='left', padx=(10, 0))

        # Canvas + real scrollbars + side details panel.
        body = ttk.Frame(wrapper, style='Panel.TFrame')
        body.pack(fill='both', expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        canvas_container = tk.Frame(body, bg=THEME['border'], bd=1)
        canvas_container.grid(row=0, column=0, sticky='nsew')
        canvas_container.columnconfigure(0, weight=1)
        canvas_container.rowconfigure(0, weight=1)

        self.tree_canvas = tk.Canvas(canvas_container, bg='#ffffff', highlightthickness=0)
        self.tree_canvas.grid(row=0, column=0, sticky='nsew')

        hbar = ttk.Scrollbar(canvas_container, orient='horizontal', command=self.tree_canvas.xview)
        hbar.grid(row=1, column=0, sticky='ew')
        vbar = ttk.Scrollbar(canvas_container, orient='vertical', command=self.tree_canvas.yview)
        vbar.grid(row=0, column=1, sticky='ns')
        self.tree_canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)

        # Drag-to-pan and wheel-to-zoom.
        self.tree_canvas.bind('<ButtonPress-1>', lambda e: self.tree_canvas.scan_mark(e.x, e.y))
        self.tree_canvas.bind('<B1-Motion>', lambda e: self.tree_canvas.scan_dragto(e.x, e.y, gain=1))
        self.tree_canvas.bind('<MouseWheel>', self._on_tree_mousewheel)
        self.tree_canvas.bind('<Button-4>', self._on_tree_mousewheel)
        self.tree_canvas.bind('<Button-5>', self._on_tree_mousewheel)

        details_container = tk.Frame(body, bg=THEME['panel_bg'], width=260)
        details_container.grid(row=0, column=1, sticky='ns', padx=(12, 0))
        details_container.grid_propagate(False)
        ttk.Label(details_container, text='Details', style='SectionTitle.TLabel').pack(anchor='w', pady=(0, 6))
        self.tree_details = tk.Text(details_container, width=30, bg='#f8fafc', fg='#16304d', wrap='word',
                                     font=(FONT_FAMILY, 10), relief='solid', bd=1, padx=8, pady=8)
        self.tree_details.pack(fill='both', expand=True)
        self._show_default_tree_tip()

    def _legend_swatch(self, parent, color, text):
        f = ttk.Frame(parent, style='Panel.TFrame')
        f.pack(side='left', padx=(0, 14))
        tk.Canvas(f, width=14, height=14, bg=THEME['panel_bg'], highlightthickness=0).pack(side='left')
        swatch = tk.Canvas(f, width=14, height=14, bg=THEME['panel_bg'], highlightthickness=0)
        swatch.place_forget()
        dot = tk.Canvas(f, width=14, height=14, bg=THEME['panel_bg'], highlightthickness=0)
        dot.pack_forget()
        c = tk.Canvas(f, width=14, height=14, bg=THEME['panel_bg'], highlightthickness=0)
        c.pack(side='left')
        c.create_oval(2, 2, 12, 12, fill=color, outline='')
        ttk.Label(f, text=text, style='Muted.TLabel').pack(side='left', padx=(4, 0))

    # -- zoom handling -------------------------------------------------
    def _on_zoom_slider(self, value):
        self.tree_zoom = float(value)
        if self.current_graph:
            self._draw_tree(self.current_graph)

    def _set_tree_zoom(self, factor):
        self.tree_zoom = max(0.3, min(3.0, self.tree_zoom * factor))
        self.tree_zoom_var.set(self.tree_zoom)
        if self.current_graph:
            self._draw_tree(self.current_graph)

    def _reset_tree_zoom(self):
        self.tree_zoom = 1.0
        self.tree_zoom_var.set(1.0)
        if self.current_graph:
            self._draw_tree(self.current_graph)
        self.tree_canvas.xview_moveto(0)
        self.tree_canvas.yview_moveto(0)

    def _on_tree_mousewheel(self, event):
        delta = getattr(event, 'delta', 0)
        if delta:
            factor = 1.1 if delta > 0 else 1 / 1.1
        else:
            factor = 1.1 if getattr(event, 'num', 0) == 4 else 1 / 1.1
        self._set_tree_zoom(factor)
        return 'break'

    # -- form helpers ----------------------------------------------------
    def _combo_value(self, key):
        widget = self.values[key]
        selected_label = widget.get()
        return self.option_maps.get(key, {}).get(selected_label, selected_label)

    def _update_approx_controls(self):
        try:
            selected = int(self._combo_value('ppa'))
        except Exception:
            selected = 1
        enabled = selected in {5, 6, 7}
        for widget in self.approx_controls:
            try:
                widget.configure(state='normal' if enabled else 'disabled')
            except Exception:
                pass

    def _read_value(self, key, entry_type='str'):
        widget = self.values[key]
        value = widget.get()
        if entry_type == 'int':
            try:
                return int(value)
            except ValueError:
                raise ValueError(f'Invalid integer value for {key}: {value}')
        return value

    # -- tree details panel ---------------------------------------------
    def _show_default_tree_tip(self):
        self.tree_details.delete('1.0', 'end')
        self.tree_details.insert('end', 'Hover over a dot or a reduction box to inspect it.\n\n'
                                         'Drag to pan, scroll to zoom, or use the controls above.')

    def _show_node_details(self, node):
        lines = []
        if node.get('kind') == 'adder':
            lines.append(f"Adder: {node['name']}")
            lines.append(f"Type: {node.get('adder_kind', node.get('kind'))}")
            lines.append(f"Approximate: {'yes' if node.get('approximate') else 'no'}")
            lines.append(f"Stage: {node['stage']}    Column: {node['column']}")
            lines.append(f"Inputs: {', '.join(node.get('inputs', [])) or 'n/a'}")
            lines.append(f"Outputs: {', '.join(node.get('outputs', [])) or 'n/a'}")
        else:
            lines.append(f"Wire: {node['name']}")
            lines.append(f"Stage: {node['stage']}    Column: {node['column']}")
            if node.get('adder'):
                lines.append(f"Consumed by: {node['adder']} ({node.get('adder_kind', '')})")
                lines.append(f"Approximate: {'yes' if node.get('approximate') else 'no'}")
                lines.append(f"Sibling inputs: {', '.join(node.get('inputs', [])) or 'n/a'}")
            else:
                lines.append('Not yet consumed by a reduction cell at this stage.')
        self.tree_details.delete('1.0', 'end')
        self.tree_details.insert('end', '\n'.join(lines))

    # -- accurate dot/box tree rendering ---------------------------------
    def _draw_tree(self, graph):
        """Draws the same stage-by-stage dot/box reduction diagram as the
        static PNG preview and the interactive HTML tree, using the shared
        layout math imported from tree_viewer.py."""
        self.current_graph = graph
        self.tree_canvas.delete('all')
        self.node_lookup = {}

        if not TREE_VIEWER_AVAILABLE:
            self.tree_canvas.create_text(250, 180, text='tree_viewer module not available',
                                          fill=THEME['danger'], font=(FONT_FAMILY, 11, 'bold'))
            return

        if not graph or (not graph.get('snapshots') and not graph.get('final_cols')):
            self.tree_canvas.create_text(250, 180, text='No tree data available yet',
                                          fill=THEME['muted'], font=(FONT_FAMILY, 12, 'bold'))
            return

        min_c = graph.get('min_column', 0)
        max_c = graph.get('max_column', 0)
        snapshots = graph.get('snapshots', [])
        final_cols = graph.get('final_cols', {})
        n_stages = graph.get('n_stages', 0)

        stages_to_draw = list(snapshots)
        if final_cols:
            stages_to_draw.append((n_stages + 1, final_cols, []))
        if not stages_to_draw:
            self.tree_canvas.create_text(250, 180, text='No reduction stages to display',
                                          fill=THEME['muted'], font=(FONT_FAMILY, 12, 'bold'))
            return

        unit = 46.0 * self.tree_zoom
        dot_r = DOT_R * unit
        dot_gap = DOT_GAP * unit
        col_gap = COL_GAP * unit
        group_gap = GROUP_GAP * unit
        stage_gap = 1.0 * unit
        left_margin = 4.6 * col_gap
        top_margin = 1.4 * unit

        def x_of(c):
            return left_margin + (max_c - c) * col_gap

        current_y = top_margin
        max_x_seen = left_margin

        for c in range(min_c, max_c + 1):
            x = x_of(c)
            max_x_seen = max(max_x_seen, x)
            self.tree_canvas.create_text(x, current_y - dot_r - 10, text=str(c),
                                          font=(FONT_FAMILY, 9, 'bold'), fill=THEME['text'])

        for i, (s, cols, active) in enumerate(stages_to_draw):
            col_adders = {}
            for a in active:
                col_adders.setdefault(a['col'], []).append(a)

            stage_top_y = current_y
            stage_bottom_y = current_y

            for c in range(min_c, max_c + 1):
                wires = cols.get(c, [])
                blocks = _ordered_blocks(wires, col_adders.get(c, []))
                y = stage_top_y
                x = x_of(c)

                for bi, (a, group) in enumerate(blocks):
                    if bi > 0:
                        y += group_gap
                    y0 = y
                    dot_ys = []
                    for _w in group:
                        dot_ys.append(y)
                        y += dot_gap
                    y1 = y - dot_gap

                    if a is not None:
                        pad = dot_r + group_gap
                        color = APPROX_COLOR if a['is_approx'] else EXACT_COLOR
                        rid = self.tree_canvas.create_rectangle(
                            x - pad, y0 - pad, x + pad, y1 + pad,
                            fill=color, outline=color, width=1)
                        info = {
                            'kind': 'adder', 'name': a['name'], 'adder_kind': a['type'],
                            'approximate': a['is_approx'], 'stage': s, 'column': c,
                            'inputs': a['inputs'], 'outputs': [a['sum'], a['carry']],
                        }
                        self.node_lookup[rid] = info
                        self.tree_canvas.tag_bind(rid, '<Enter>', lambda e, n=info: self._show_node_details(n))
                        self.tree_canvas.tag_bind(rid, '<Leave>', lambda e: self._show_default_tree_tip())

                    for w, wy in zip(group, dot_ys):
                        oid = self.tree_canvas.create_oval(
                            x - dot_r, wy - dot_r, x + dot_r, wy + dot_r,
                            fill=DOT_COLOR, outline='')
                        info = {
                            'kind': 'wire', 'name': w, 'stage': s, 'column': c,
                            'adder': a['name'] if a else None,
                            'adder_kind': a['type'] if a else None,
                            'approximate': a['is_approx'] if a else False,
                            'inputs': a['inputs'] if a else [],
                        }
                        self.node_lookup[oid] = info
                        self.tree_canvas.tag_bind(oid, '<Enter>', lambda e, n=info: self._show_node_details(n))
                        self.tree_canvas.tag_bind(oid, '<Leave>', lambda e: self._show_default_tree_tip())

                    stage_bottom_y = max(stage_bottom_y, y)

                max_x_seen = max(max_x_seen, x)

            label = f'STAGE {s}' if i < len(stages_to_draw) - 1 else 'RCA STAGE'
            label_x = left_margin - 2.2 * col_gap
            label_y = (stage_top_y + stage_bottom_y) / 2
            self.tree_canvas.create_text(label_x, label_y, text=label, angle=90,
                                          font=(FONT_FAMILY, 9, 'bold'), fill=THEME['text'])

            current_y = stage_bottom_y + stage_gap
            if i < len(stages_to_draw) - 1:
                line_y = current_y - stage_gap * 0.45
                self.tree_canvas.create_line(
                    left_margin - 3.0 * col_gap, line_y, max_x_seen + col_gap * 1.8, line_y,
                    fill=THEME['danger'], width=1, stipple='gray50')

        total_w = max_x_seen + col_gap * 2.0
        total_h = current_y + stage_gap
        self.tree_canvas.configure(scrollregion=(0, 0, total_w, total_h))

    def _show_preview_image(self, image_path):
        image_path = Path(image_path)
        if not image_path.exists():
            return

        try:
            from PIL import Image, ImageTk
            img = Image.open(image_path).convert('RGBA')
            max_w = max(720, int(self.tree_canvas.winfo_width() or 720))
            max_h = max(440, int(self.tree_canvas.winfo_height() or 440))
            img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            self.tree_photo = ImageTk.PhotoImage(img)
            self.tree_canvas.delete('all')
            self.tree_canvas.create_image(0, 0, anchor='nw', image=self.tree_photo)
            self.tree_canvas.configure(scrollregion=(0, 0, img.width, img.height))
            self.tree_details.delete('1.0', 'end')
            self.tree_details.insert('end', f'Preview image:\n{image_path}')
        except Exception:
            self.tree_canvas.delete('all')
            self.tree_canvas.create_text(20, 20, anchor='nw', text=f'Preview: {image_path}',
                                          fill=THEME['text'], font=(FONT_FAMILY, 10, 'bold'))

    def _generate_dadda_tree_image(self, verilog_path=None):
        selected = verilog_path
        if selected is None:
            generated_files = sorted(ROOT.glob('*_GenMul.v'))
            if not generated_files:
                messagebox.showinfo('No Verilog yet', 'Generate a design first to create the Dadda tree image.')
                return None
            selected = generated_files[-1]

        try:
            import importlib.util
            dadda_path = ROOT / 'src' / 'DaddaImage.py'
            spec = importlib.util.spec_from_file_location('dadda_image_tool', dadda_path)
            dadda_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(dadda_module)

            text = Path(selected).read_text(encoding='utf-8', errors='ignore')
            module_name = dadda_module.choose_target_module(text)
            instances, module_body = dadda_module.parse_module_instances(text, module_name)
            adders, stage_of, col_of, _ = dadda_module.build_schedule(instances, module_body)
            snapshots, final_cols, _ = dadda_module.simulate_columns(adders, stage_of, col_of)
            if not snapshots:
                messagebox.showinfo('No reduction data', 'The generated design does not contain a reducible Dadda stage.')
                return None

            out_path = Path(selected).with_name(Path(selected).stem + '_dadda.png')
            min_c = min(col_of.values()) if col_of else 0
            max_c = max(col_of.values()) if col_of else 0
            dadda_module.render_combined(snapshots, final_cols, str(out_path), min_c, max_c)
            self._show_preview_image(out_path)

            self.set_status(f'Dadda reduction image created: {out_path.name}')
            return out_path
        except Exception as exc:
            messagebox.showerror('Dadda image failed', f'Could not create the tree image from the tool: {exc}')
            return None

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    def generate_design(self):
        if not BINARY.exists():
            messagebox.showerror('Missing binary', f'Could not find the GenMul executable at: {BINARY}\nPlease build the project first.')
            return

        try:
            ppg = int(self._combo_value('ppg'))
            ppa = int(self._combo_value('ppa'))
            fsa = int(self._combo_value('fsa'))
            in1 = int(self._read_value('in1', 'int'))
            in2 = int(self._read_value('in2', 'int'))
            col = int(self._read_value('col', 'int'))
            cout = int(self._read_value('cout', 'int'))
            sum_mask = int(self._read_value('sum', 'int'))
            method = int(self._combo_value('method'))
            debug = int(self._combo_value('debug'))
        except ValueError as exc:
            messagebox.showerror('Invalid input', str(exc))
            return

        if ppa in {5, 6, 7}:
            if not (0 <= col <= in1 + in2 - 2):
                messagebox.showerror('Invalid input', f'Approximation column must be between 0 and {in1 + in2 - 2}.')
                return
            if not (0 <= cout <= 255):
                messagebox.showerror('Invalid input', 'Carry mask must be between 0 and 255.')
                return
            if not (0 <= sum_mask <= 255):
                messagebox.showerror('Invalid input', 'Sum mask must be between 0 and 255.')
                return
            if not (0 <= method <= 3):
                messagebox.showerror('Invalid input', 'Approximation method must be between 0 and 3.')
                return
            if not (debug in {0, 1}):
                messagebox.showerror('Invalid input', 'Debug mode must be 0 or 1.')
                return
            args = [str(ppg), str(ppa), str(fsa), str(in1), str(in2), str(col), str(cout), str(sum_mask), str(method), str(debug)]
        else:
            args = [str(ppg), str(ppa), str(fsa), str(in1), str(in2)]

        self.set_status('Generating RTL…')
        try:
            subprocess.run([str(BINARY), *args], cwd=str(ROOT), check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as exc:
            self.set_status('Generation failed.')
            messagebox.showerror('Generation failed', exc.output.decode('utf-8', errors='replace'))
            return

        generated_files = sorted(ROOT.glob(f'{in1}_{in2}_*GenMul.v'))
        if not generated_files:
            self.set_status('No output file produced.')
            messagebox.showerror('No output file', 'No Verilog output file was created.')
            return

        latest = generated_files[-1]
        output_path = latest
        html_path = str(output_path).replace('.v', '.html')

        if debug == 1:
            self.output_text.delete('1.0', 'end')
            self.output_text.insert('end', f'Generated Verilog: {output_path}\nDebug mode is enabled; tree preview is intentionally skipped for now.')
            self.notebook.select(self.results_frame)
            self.set_status('Generated (debug mode — tree preview skipped).')
            return

        try:
            generate_tree_html(str(output_path), html_path)
            graph = parse_verilog_tree(output_path.read_text(encoding='utf-8', errors='ignore'))
            self._draw_tree(graph)
            self._generate_dadda_tree_image(output_path)
        except Exception as exc:
            self.set_status('Tree generation failed.')
            messagebox.showerror('Tree generation failed', f'Could not build the tree view: {exc}')
            return

        self.output_text.delete('1.0', 'end')
        self.output_text.insert('end', f'Generated Verilog: {output_path}\nGenerated HTML tree: {html_path}\nDadda reduction image created in the Tree Preview tool flow.\nTree preview is active in the Tree Preview tab.')
        self.notebook.select(self.tree_frame)
        self.set_status(f'Design generated: {output_path.name}')

    def open_tree_view(self):
        candidates = sorted(ROOT.glob('*_GenMul.html'))
        if not candidates:
            messagebox.showinfo('No tree yet', 'Generate a design first to create the tree viewer.')
            return
        html_path = str(candidates[-1])
        webbrowser.open('file://' + html_path)

    def export_tree_html(self):
        candidates = sorted(ROOT.glob('*_GenMul.html'))
        if not candidates:
            messagebox.showinfo('No tree yet', 'Generate a design first to create the tree viewer.')
            return

        source = candidates[-1]
        export_path = filedialog.asksaveasfilename(
            title='Save Tree HTML',
            initialfile=source.name,
            defaultextension='.html',
            filetypes=[('HTML files', '*.html'), ('All files', '*.*')],
            initialdir=str(ROOT),
        )
        if not export_path:
            return

        try:
            import shutil
            shutil.copy2(str(source), export_path)
            self.set_status(f'HTML exported: {export_path}')
            messagebox.showinfo('Export complete', f'Tree HTML saved to:\n{export_path}')
        except Exception as exc:
            self.set_status('Export failed.')
            messagebox.showerror('Export failed', f'Could not save the HTML tree:\n{exc}')


def main():
    root = tk.Tk()
    app = GenMulApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()