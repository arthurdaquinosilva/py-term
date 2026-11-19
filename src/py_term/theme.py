"""The color palette shared by the prompt (prompt_toolkit), output (rich) and syntax (pygments)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

from prompt_toolkit.styles import BaseStyle, merge_styles, style_from_pygments_cls
from prompt_toolkit.styles import Style as PTStyle
from pygments.style import Style as PygmentsStyle
from pygments.token import (
    Comment,
    Error,
    Generic,
    Keyword,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
    Text,
    Token,
)
from rich.syntax import PygmentsSyntaxTheme
from rich.theme import Theme as RichTheme


@dataclass(frozen=True)
class Palette:
    name: str
    fg: str
    muted: str
    faint: str
    border: str
    surface: str
    selection: str
    bar: str  # filled input bar
    label: str  # key-bar labels and banner values
    accent: str
    accent2: str
    ok: str
    err: str
    warn: str
    info: str
    # syntax
    keyword: str
    builtin: str
    function: str
    klass: str
    string: str
    number: str
    comment: str
    operator: str
    decorator: str


PALETTES: dict[str, Palette] = {
    # pitch: cool blue/violet hues on a pitch-black terminal, shared by all the tools;
    # each one gets its own accent (:py's is orange).
    "pitch": Palette(
        name="pitch",
        fg="#c0caf5",
        muted="#737aa2",
        faint="#565f89",
        border="#2a2e42",
        surface="#0b0d14",
        selection="#161925",
        bar="#161925",
        label="#bb9af7",
        accent="#ff9e64",
        accent2="#e0af68",
        ok="#9ece6a",
        err="#f7768e",
        warn="#e0af68",
        info="#7aa2f7",
        keyword="#bb9af7",
        builtin="#7dcfff",
        function="#7aa2f7",
        klass="#73daca",
        string="#9ece6a",
        number="#ff9e64",
        comment="#565f89",
        operator="#a9b1d6",
        decorator="#e0af68",
    ),
}

DEFAULT_THEME = "pitch"


class Theme:
    def __init__(self, palette: Palette):
        self.p = palette

    @property
    def name(self) -> str:
        return self.p.name

    @cached_property
    def pygments_style(self) -> type[PygmentsStyle]:
        p = self.p
        return type(
            f"PyTerm{p.name.title()}Style",
            (PygmentsStyle,),
            {
                "background_color": None,
                "highlight_color": p.selection,
                "styles": {
                    Token: p.fg,
                    Text: p.fg,
                    Comment: f"italic {p.comment}",
                    Keyword: p.keyword,
                    Keyword.Constant: p.number,
                    Keyword.Namespace: p.keyword,
                    Operator: p.operator,
                    Operator.Word: p.keyword,
                    Punctuation: p.operator,
                    Name: p.fg,
                    Name.Builtin: p.builtin,
                    Name.Builtin.Pseudo: f"italic {p.builtin}",
                    Name.Function: p.function,
                    Name.Function.Magic: p.builtin,
                    Name.Class: f"bold {p.klass}",
                    Name.Decorator: p.decorator,
                    Name.Exception: p.klass,
                    Name.Namespace: p.klass,
                    Name.Variable.Magic: p.builtin,
                    String: p.string,
                    String.Doc: f"italic {p.comment}",
                    String.Escape: p.number,
                    String.Interpol: p.accent2,
                    String.Affix: p.keyword,
                    Number: p.number,
                    Generic.Deleted: p.err,
                    Generic.Inserted: p.ok,
                    Generic.Heading: f"bold {p.fg}",
                    Generic.Subheading: p.muted,
                    Generic.Error: p.err,
                    Generic.Traceback: p.err,
                    Error: p.err,
                },
            },
        )

    @cached_property
    def syntax_theme(self) -> PygmentsSyntaxTheme:
        return PygmentsSyntaxTheme(self.pygments_style)

    @cached_property
    def pt_style(self) -> BaseStyle:
        p = self.p
        ui = PTStyle.from_dict(
            {
                "": p.fg,
                "bar": f"bg:{p.bar}",
                "bar.prompt": f"bg:{p.bar} bold {p.accent}",
                "bar.cont": f"bg:{p.bar} {p.faint}",
                "bar.count": f"bg:{p.bar} {p.faint}",
                "placeholder": p.faint,
                "rule": p.border,
                "rule.prompt": p.muted,
                "rule.prompt.cont": p.faint,
                "footer.mode": p.muted,
                "footer.hint": p.faint,
                "shortcut.key": f"bold {p.muted}",
                "shortcut.desc": p.faint,
                "keybar.label": f"bold {p.label}",
                "keybar.key": p.fg,
                "keybar.sep": p.faint,
                "modeline.mode": f"bold {p.label}",
                "box.border": p.border,
                "box.border.active": p.faint,
                "box.title": f"bold {p.accent}",
                "box.label": p.faint,
                "prompt": f"bold {p.accent}",
                "prompt.cont": p.faint,
                "status": p.muted,
                "status.dim": p.faint,
                "status.accent": p.accent,
                "status.ok": p.ok,
                "status.err": p.err,
                "status.warn": p.warn,
                "status.key": f"{p.fg}",
                "status.sep": p.faint,
                "sig.icon": p.accent,
                "sig.name": f"bold {p.builtin}",
                "sig.param": p.muted,
                "sig.param.current": f"bold underline {p.accent}",
                "sig.type": p.klass,
                "sig.type.inferred": f"italic {p.muted}",
                "sig.return": f"bold {p.klass}",
                "sig.default": p.faint,
                "sig.punct": p.faint,
                "auto-suggestion": p.faint,
                "matching-bracket.cursor": f"bg:{p.selection} bold",
                "matching-bracket.other": f"bg:{p.selection} bold",
                "selected": f"bg:{p.selection}",
                # prompt_toolkit paints the menu light grey and reverses the current row onto white:
                # set every background, or light text lands on a light box
                "completion-menu": f"bg:{p.surface} {p.fg}",
                "completion-menu.completion": f"bg:{p.surface} {p.fg}",
                "completion-menu.completion.current": f"noreverse bg:{p.selection} bold {p.accent}",
                "completion-menu.meta.completion": f"bg:{p.surface} {p.faint}",
                "completion-menu.meta.completion.current": f"bg:{p.selection} {p.muted}",
                "completion-menu.multi-column-meta": f"bg:{p.surface} {p.muted}",
                "completion-menu.completion fuzzymatch.outside": p.muted,
                "completion-menu.completion fuzzymatch.inside": f"bold {p.fg}",
                "completion-menu.completion.current fuzzymatch.outside": p.accent,
                # after the popup rules so these win: the rule layout lists completions under the prompt, like :sql: no box, accent on the current one
                "inline completion-menu": f"bg:default {p.fg}",
                "inline completion-menu.completion": f"bg:default {p.fg}",
                "inline completion-menu.completion.current": f"noreverse bg:default bold {p.accent}",
                "inline completion-menu.meta.completion": f"bg:default {p.faint}",
                "inline completion-menu.meta.completion.current": f"bg:default {p.accent}",
                "inline completion-menu.multi-column-meta": f"bg:default {p.muted}",
                "inline scrollbar.background": "bg:default",
                "comp.icon": p.faint,
                "comp.icon.function": p.builtin,
                "comp.icon.class": p.klass,
                "comp.icon.module": p.decorator,
                "comp.icon.keyword": p.keyword,
                "comp.icon.instance": p.string,
                "comp.icon.magic": p.accent,
                "comp.icon.path": p.accent2,
                "scrollbar.background": f"bg:{p.surface}",
                "scrollbar.button": f"bg:{p.border}",
                "search": f"bg:{p.selection}",
                "search.current": f"bg:{p.accent} #000000",
                "search-toolbar": p.muted,
                "search-toolbar.prompt": f"bold {p.accent}",
                "search-toolbar.text": p.fg,
            }
        )
        return merge_styles([style_from_pygments_cls(self.pygments_style), ui])

    @cached_property
    def rich_theme(self) -> RichTheme:
        p = self.p
        return RichTheme(
            {
                "py_term.fg": p.fg,
                "py_term.muted": p.muted,
                "py_term.faint": p.faint,
                "py_term.border": p.border,
                "py_term.accent": p.accent,
                "py_term.accent2": p.accent2,
                "py_term.ok": p.ok,
                "py_term.err": p.err,
                "py_term.warn": p.warn,
                "py_term.info": p.info,
                "py_term.label": f"bold {p.label}",
                "py_term.accent.bold": f"bold {p.accent}",
                "py_term.accent.blink": f"bold blink {p.accent}",
                "py_term.err.bold": f"bold {p.err}",
                "py_term.fg.bold": f"bold {p.fg}",
                "py_term.info.bold": f"bold {p.info}",
                "py_term.keyword": p.keyword,
                "py_term.class": p.klass,
                "py_term.string": p.string,
                "repr.number": p.number,
                "repr.number_complex": p.number,
                "repr.str": p.string,
                "repr.bool_true": f"italic {p.ok}",
                "repr.bool_false": f"italic {p.err}",
                "repr.none": f"italic {p.muted}",
                "repr.ellipsis": p.faint,
                "repr.brace": p.operator,
                "repr.comma": p.faint,
                "repr.call": p.builtin,
                "repr.attrib_name": p.klass,
                "repr.attrib_equal": p.faint,
                "repr.attrib_value": p.fg,
                "repr.tag_name": p.klass,
                "repr.tag_start": p.faint,
                "repr.tag_end": p.faint,
                "repr.tag_contents": p.fg,
                "repr.url": f"underline {p.info}",
                "repr.path": p.decorator,
                "repr.filename": p.accent2,
                "repr.uuid": p.accent2,
                "repr.ipv4": p.info,
                "repr.ipv6": p.info,
                "repr.eui48": p.info,
                "repr.eui64": p.info,
                "repr.indent": p.border,
                "pretty.indent": p.border,
                "traceback.border": p.err,
                "traceback.border.syntax_error": p.err,
                "traceback.title": f"bold {p.err}",
                "traceback.exc_type": f"bold {p.err}",
                "traceback.exc_value": p.fg,
                "traceback.offset": f"bold {p.err}",
                "traceback.error": f"bold {p.err}",
                "traceback.error_range": f"underline {p.err}",
                "traceback.note": p.warn,
                "traceback.group.border": p.warn,
                "table.header": f"bold {p.accent}",
                "table.footer": p.muted,
                "table.caption": f"italic {p.muted}",
                "rule.line": p.border,
            }
        )


def get_theme(name: str | None) -> Theme:
    return Theme(PALETTES.get(name or DEFAULT_THEME, PALETTES[DEFAULT_THEME]))
