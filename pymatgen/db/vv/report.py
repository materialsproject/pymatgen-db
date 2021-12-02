"""
Description.
"""
__author__ = "Dan Gunter <dkgunter@lbl.gov>"
__date__ = "2/21/13"


from email.mime.text import MIMEText
import json
from operator import itemgetter
import smtplib

#
from .util import DoesLogging, JsonWalker
from ..util import MongoJSONEncoder
from .diff import Differ, Delta  # for field constants, formatting


class Report:
    def __init__(self, header):
        """Create blank report, with a header.

        :param header: Report header
        :type header: Header
        """
        self._hdr = header
        self._sections = []

    def add_section(self, section):
        self._sections.append(section)

    @property
    def header(self):
        return self._hdr

    def is_empty(self):
        if len(self._sections) == 0:
            return True
        self._total_rows = 0
        for sect in self._sections:
            self._count_rows(sect)
        return self._total_rows == 0

    def _count_rows(self, sect):
        if sect.body is not None:
            self._total_rows += sect.body.nrow
        for subsect in sect._sections:
            self._count_rows(subsect)

    def __iter__(self):
        return iter(self._sections)


class ReportSection(Report):
    """Section within a report, with data."""

    def __init__(self, header, body=None):
        """Create new report section, initialized with header and body.

        :param header: The header for the section
        :type header: SectionHeader
        :param body: The body of the section, or None if this is a container for sub-sections
        :type body: Table
        """
        Report.__init__(self, header)
        self._body = body

    @property
    def body(self):
        return self._body


class Header:
    """Base header class."""

    def __init__(self, title=""):
        self._kv = []
        self.title = title

    def add(self, key, value):
        self._kv.append((key, value))

    def get(self, key):
        return (v for k, v in self._kv if k == key)

    def __iter__(self):
        return iter(self._kv)

    def as_dict(self):
        return {k: v for k, v in self._kv}


class ReportHeader(Header):
    """Header for entire report."""

    pass


class SectionHeader(Header):
    """Header for one section of a report."""

    pass


class Table:
    """Table of values."""

    def __init__(self, colnames):
        self._colnames = colnames
        self._rows = []
        self._width = len(colnames)
        self._max_col_widths = list(map(len, colnames))

    def add(self, values):
        if len(values) != self._width:
            raise ValueError(f"expected {self._width:d} values, got {len(values):d}")
        self._rows.append(values)
        for i, v in enumerate(values):
            n = len(str(v))
            if self._max_col_widths[i] < n:
                self._max_col_widths[i] = n

    def sortby(self, name_or_index):
        name, index = None, None
        if isinstance(name_or_index, int):
            index = name_or_index
        else:
            name = name_or_index
        if name is not None:
            try:
                colnum = self._colnames.index(name)
            except ValueError:
                raise ValueError(f"column {name} not in {self._colnames}")
        else:
            if index < 0 or index >= self._width:
                raise ValueError(f"index out of range 0..{self._width - 1:d}")
            colnum = index
        self._rows.sort(key=itemgetter(colnum))

    def __iter__(self):
        return iter(self._rows)

    @property
    def values(self):
        return [{self._colnames[i]: r[i] for i in range(self._width)} for r in self._rows]

    @property
    def column_names(self):
        return self._colnames

    @property
    def column_widths(self):
        return self._max_col_widths

    @property
    def ncol(self):
        return self._width

    @property
    def nrow(self):
        return len(self._rows)


## Exceptions


class ReportBackupError(Exception):
    pass


## Formatting


def css_minify(s):
    # return s.replace('\n', ' ').replace('  ', ' ')
    s = s.replace("{ ", "{")
    s = s.replace(" }", "}")
    return s


# CSS for HTML report output
DEFAULT_CSS = [
    "html { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }",
    "body { margin: 2em;}",
    "table { margin-top: 1em; clear: both; border: 0;}",
    "dl, dt, dd { float: left; }",
    "dl, dt { clear: both; }",
    "dt { width: 8em; font-weight: 700; }",
    "dd { width: 32em; }",
    "tr:nth-child(even) { background-color: #E9E9E9; }",
    "tr:nth-child(odd) { background-color: #E9E9E9; }",
    "th, td {padding: 0.2em 0.5em;}",
    "th { text-align: left;  color: black; margin: 0; font-weight: 300;}",
    "h1, h2, h3 { clear: both; margin: 0; padding: 0; }",
    "h1 { font-size: 18; color: rgb(44, 62, 80); }",
    "h2 { font-size: 14; color: black; }",
]


class HTMLFormatter:
    """Format a report as HTML."""

    def __init__(self, line_sep="\n", id_column=0, css=None):
        self._sep = line_sep
        self._idcol = id_column
        if css is None:
            css = DEFAULT_CSS
        self._css = css

    def format(self, report):
        text = []
        text.append("<!DOCTYPE html>")
        text.append("<html>")
        text.append(f"<title>{report.header.title}</title>")
        text.append("<head>")
        if self._css:
            text.append("<style>")
            text.append("\r\n".join(self._css))
            text.append("</style>")
        text.append("</head>")
        text.append("<body>")
        text.append(f"<h1>{report.header.title}</h1>")
        text.append('<dl class="rptmeta">')
        for key, value in report.header:
            text.append(f"<dt>{key}</dt>")
            text.append(f"<dd>{value}</dd>")
        text.append("</dl>")
        for section in report:
            text.append(f"<h2>{section.header.title}</h2>")
            text.append('<dl class="sectmeta">')
            for key, value in section.header:
                text.append(f"<dt>{key}</dt>")
                text.append(f"<dd>{value}</dd>")
            text.append("</dl>")
            for cond_section in section:
                text.append(f"<h3>{cond_section.header.title}</h3>")
                text.append('<dl class="subsectmeta">')
                for key, value in cond_section.header:
                    text.append(f"<dt>{key}</dt>")
                    text.append(f"<dd>{value}</dd>")
                text.append("</dl>")
                text.append("<table>")
                text.append("<tr>")
                for name in cond_section.body.column_names:
                    text.append(f"<th>{name}</th>")
                text.append("</tr>")
                prev_key, i = None, 0
                for row in cond_section.body:
                    row = list(row)
                    key = row[self._idcol]
                    if prev_key and key == prev_key:
                        row[self._idcol] = ""
                    else:
                        prev_key = key
                        i += 1
                    rclass = ("even", "odd")[i % 2]
                    text.append(f'<tr class="{rclass}">')
                    for value in row:
                        text.append(f"<td>{value}</td>")
                    text.append("</tr>")
                text.append("</table>")
        text.append("</body>")
        text.append("</html>")
        text_str = self._sep.join(text)
        text_str = text_str.replace("**", "<br>")
        return text_str


class JSONFormatter:
    """Format a report as JSON."""

    def __init__(self, id_column=0, indent=2):
        self._indent = indent
        self._idcol = id_column

    def format(self, report):
        obj = dict(
            title=report.header.title,
            info=report.header,
            sections=[
                dict(
                    title=s.header.title,
                    info=s.header,
                    conditions=[dict(title=cs.header.title, info=cs.header, violations=cs.body) for cs in s],
                )
                for s in report
            ],
        )
        return json.dumps(obj, indent=self._indent, cls=MongoJSONEncoder)


class ReportJSONEncoder(MongoJSONEncoder):
    def default(self, o):
        if isinstance(o, Header):
            return o.as_dict()
        elif isinstance(o, Table):
            return o.values
        return MongoJSONEncoder.default(self, o)


class MarkdownFormatter:
    """Format a report as markdown"""

    def __init__(self, id_column=0):
        self._idcol = id_column

    def _mapdump(self, d):
        return ", ".join((f"{k}={v}" for k, v in d.items()))

    def _fixed_width(self, values, widths):
        s = "".join([f"{{:{w + 1:d}s}}".format(str(v)) for w, v in zip(widths, values)])
        return s

    def format(self, report):
        lines = []
        self._append_heading(lines, 1, report.header.title)
        self._append_info_section(lines, report.header)
        for section in report:
            self._append_heading(lines, 2, section.header.title)
            self._append_info_section(lines, section.header)
            for cond in section:
                self._append_heading(lines, 3, cond.header.title)
                self._append_info_section(lines, cond.header)
                self._append_violations(lines, cond.body)
        return "\n".join(lines)

    def _append_info_section(self, lines, info):
        if not info:
            return
        infodict = info.as_dict()
        if infodict:
            text = f"Info: {self._mapdump(infodict)}"
            lines.append(text)

    def _append_heading(self, lines, level, title):
        hashes = "#" * level
        text = f"\n{hashes} {title} {hashes}\n"
        lines.append(text)

    def _append_violations(self, lines, data):
        lines.append("\nViolations:\n")
        indent = "    "
        lines.append(indent + self._fixed_width(data.column_names, data.column_widths))
        for row in data:
            lines.append(indent + self._fixed_width(row, data.column_widths))


class Emailer(DoesLogging):
    """Send a report to an email recipient."""

    def __init__(
        self,
        sender="me@localhost",
        recipients=("you@remote.host",),
        subject="Report",
        server="localhost",
        port=None,
        **kwargs,
    ):
        """Send reports as email.

        :param: sender Sender of the email
        :param: recipients List of _recipients of the email
        :param: subject Email _subject line
        :param: server SMTP server host
        :param: port SMTP server port (None for default)
        """
        DoesLogging.__init__(self, "mg.emailer")
        self._sender, self._recipients, self._subject = (sender, recipients, subject)
        self._server, self._port = server, port
        self._message = ""

    @property
    def subject(self):
        return self._subject

    @subject.setter
    def subject(self, value):
        self._subject = value

    def send(self, text, fmt):
        """Send the email message.

        :param text: The text to send
        :type text: str
        :param fmt: The name of the format of the text
        :type fmt: str
        :return: Number of recipients it was sent to
        :rtype: int
        """
        main_fmt, sub_fmt = fmt.split("/")
        if sub_fmt.lower() == "text":
            msg = MIMEText(text, "plain")
        elif sub_fmt.lower() == "html":
            msg = MIMEText(text, "html")
        else:
            raise ValueError(f"Unknown message format: {fmt}")
        msg["Subject"] = self._subject
        msg["From"] = self._sender
        msg["To"] = ", ".join(self._recipients)
        if self._port is None:
            conn_kwargs = dict(host=self._server)
        else:
            conn_kwargs = dict(host=self._server, port=self._port)
        self._log.info(f"connect to email server {conn_kwargs}")
        try:
            s = smtplib.SMTP(**conn_kwargs)
            # s.set_debuglevel(2)
            refused = s.sendmail(self._sender, self._recipients, msg.as_string())
            if refused:
                self._log.warn(f"Email to {len(refused):d} recipients was refused")
                for person, (code, msg) in refused.items():
                    self._log(f"Email to {person} was refused ({code}): {msg}")
            s.quit()
            n_recip = len(self._recipients)
        except Exception as err:
            self._log.error(f"connection to SMTP server failed: {err}")
            n_recip = 0
        return n_recip


# ---------------
# Diff formatting
# ---------------


class DiffFormatter:
    """Base class for formatting a 'diff' report."""

    TITLE = "Materials Project Database Diff Report"

    def __init__(self, meta, key=None):
        """Constructor.

        :param meta: Report metadata, must have the following keys:
                     - start_time, end_time: string repr of report gen. times
                     - elapsed: float #sec for end_time - start_time
                     - db1, db2: string repr of 2 input database/collections.
        :type meta: dict
        :param key: Record key field
        :type key: str
        """
        self.meta = meta
        self.key = key

    def format(self, result):
        """Format a report from a result object.

        :return: Report body
        :rtype: str
        """
        raise NotImplementedError()

    def result_subsets(self, rs):
        """Break a result set into subsets with the same keys.

        :param rs: Result set, rows of a result as a list of dicts
        :type rs: list of dict
        :return: A set with distinct keys (tuples), and a dict, by these tuples, of max. widths for each column
        """
        keyset, maxwid = set(), {}
        for r in rs:
            key = tuple(sorted(r.keys()))
            keyset.add(key)
            if key not in maxwid:
                maxwid[key] = [len(k) for k in key]
            for i, k in enumerate(key):
                strlen = len(f"{r[k]}")
                maxwid[key][i] = max(maxwid[key][i], strlen)
        return keyset, maxwid

    def ordered_cols(self, columns, section):
        """Return ordered list of columns, from given columns and the name of the section"""
        columns = list(columns)  # might be a tuple
        fixed_cols = [self.key]
        if section.lower() == "different":
            fixed_cols.extend([Differ.CHANGED_MATCH_KEY, Differ.CHANGED_OLD, Differ.CHANGED_NEW])
        map(columns.remove, fixed_cols)
        columns.sort()
        return fixed_cols + columns

    def sort_rows(self, rows, section):
        """Sort the rows, as appropriate for the section.

        :param rows: List of tuples (all same length, same values in each position)
        :param section: Name of section, should match const in Differ class
        :return: None; rows are sorted in-place
        """
        # print("@@ SORT ROWS:\n{}".format(rows))
        # Section-specific determination of sort key
        if section.lower() == Differ.CHANGED.lower():
            sort_key = Differ.CHANGED_DELTA
        else:
            sort_key = None
        if sort_key is not None:
            rows.sort(key=itemgetter(sort_key))


class DiffJsonFormatter(DiffFormatter):
    class Encoder(json.JSONEncoder):
        def default(self, o):
            if hasattr(o, "as_json"):
                return o.as_json()
            return json.JSONEncoder.default(self, o)

    #    class Manipulator(pymongo.son_manipulator.SONManipulator):
    #        def transform_incoming(self, son, collection):
    #            return walk(son, visit_as_json, None)

    def __init__(self, meta, pretty=False, **kwargs):
        """Constructor.

        :param meta: see superclass
        :param pretty: Indented format
        :type pretty: bool
        """
        DiffFormatter.__init__(self, meta, **kwargs)
        self._indent = 4 if pretty else None

    def will_copy(self):
        return True

    def _add_meta(self, result):
        # put metadata into its own section
        result["meta"] = self.meta
        # .. but promote a timestamp, for searching
        result["time"] = self.meta["end_time"]

    def format(self, result):
        self._add_meta(result)
        return json.dumps(result, cls=self.Encoder, indent=self._indent)

    def document(self, result):
        """Build dict for MongoDB, expanding result keys as we go."""
        self._add_meta(result)
        walker = JsonWalker(JsonWalker.value_json, JsonWalker.dict_expand)
        r = walker.walk(result)
        return r


class DiffHtmlFormatter(DiffFormatter):
    """Format an HTML diff report."""

    DIFF_CSS = [
        ".header {padding: 5px; margin: 0 5px;}",
        ".header h1 {color: #165F4B; font-size: 20; text-align: left; margin-left: 20px;}",
        ".header p {color: #666666; margin-left: 20px; height: 12px;}",
        ".header p em {color: #4169E1; font-style: normal;}",
        ".content {padding: 15px; padding-top: 0px; margin: 0; background-color: #F3F3F3;}",
        ".content h2 {color: #2C3E50; font-size: 16px;}",
        ".empty { font-size: 14px; font-style: italic;}",
        ".section {padding: 5px; margin: 10px; background-color: #E2E2E2; border-radius: 5px;}",
        ".section div {margin-left: 10px;}",
        ".section table {margin-left: 5px;}",
        "tr:nth-child(even) { background-color: white; }",
        "tr:nth-child(odd) { background-color: #F5F5F5; }",
        "tr:nth-child(1) { background-color: #778899; font-weight: 500;}",
        "th, td {padding: 0.2em 0.5em;}",
        "th { text-align: left;  color: white; margin: 0;}",
        ".fixed { font-family: Consolas, monaco, monospace; }",
    ]
    css = DEFAULT_CSS + DIFF_CSS

    # for email inlining
    styles = {
        "header": {
            "h1": "color: #165F4B; font-size: 20; text-align: left; margin-left: 20px",
            "p": "color: #666666; margin-left: 20px; height: 12px",
            "em": "color: #4169E1; font-style: normal",
        },
        "content": {
            "_": "padding: 15px; padding-top: 0px; margin: 0; background-color: #F3F3F3",
            "h2": "color: #2C3E50; font-size: 16px",
            "section": "padding: 5px; margin: 10px; background-color: #E2E2E2; border-radius: 5px",
        },
        "table": {
            "table": "margin-top: 1em; clear: both; border: 0",
            "tr_even": "background-color: white",
            "tr_odd": "background-color: #F5F5F5",
            "tr1": "background-color: #778899; font-weight: 500",
            "th": "text-align: left;  color: white; margin: 0; padding: 0.2em 0.5em",
            "td": "padding: 0.2em 0.5em",
        },
    }

    def __init__(self, meta, url=None, email_mode=False, **kwargs):
        """Constructor.

        :param meta: see superclass
        :param url: Optional URL to create hyperlink for keys
        :type url: str
        """
        DiffFormatter.__init__(self, meta, **kwargs)
        self._url = url
        self._email = email_mode

    def format(self, result):
        """Generate HTML report.

        :return: Report body
        :rtype: str
        """
        css = "\n".join(self.css)
        content = f"{self._header()}{self._body(result)}"
        if self._email:
            text = """<!DOCTYPE html>
            <html>
            <div width="100%" style="{sty}">{content}</div>
            </html>
            """.format(
                content=content, sty=self.styles["content"]["_"]
            )
        else:
            text = """<html>
            <head><style>{css}</style></head>
            <body>{content}</body>
            </html>
            """.format(
                css=css, content=content
            )
        return text

    def _header(self):
        lines = [
            f"<div class='header'><h1{{sh1}}>{self.TITLE}</h1>",
            "<p{sp}>Compared <em{sem}>{{db1}}</em> with <em{sem}>{{db2}}</em></p>",
            "<p{sp}>Filter: <span class='fixed'>{{filter}}</span></p>",
            "<p{sp}>Run time: <em{sem}>{{start_time}}</em> to <em{sem}>{{end_time}}</em> ",
            "(<em{sem}>{{elapsed:.1f}}</em> sec)</p>",
            "</div>",
        ]
        if self._email:  # inline the styles
            _c = "header"
            _f = lambda s: s.format(
                sp=self.style(_c, "p"),
                sem=self.style(_c, "em"),
                sh1=self.style(_c, "h1"),
            )
        else:
            _f = lambda s: s.format(sp="", sem="", sh1="")
        lines = map(_f, lines)
        s = "\n".join(lines)
        return s.format(**self.meta)

    def style(self, css_class, elt):
        s = ""
        if css_class in self.styles and elt in self.styles[css_class]:
            s = f" style='{self.styles[css_class][elt]}'"
        return s

    def _body(self, result):
        body = ["<div class='content'>"]
        for section in result.keys():
            body.append(f"<div class='section'{{ssec}}><h2{{sh2}}>{section.title()}</h2>")
            if len(result[section]) == 0:
                body.append("<div class='empty'>Empty</div>")
            else:
                body.extend(self._table(section, result[section]))
            body.append("</div>")
        body.append("</div>")
        if self._email:
            _c = "content"
            _f = lambda s: s.format(
                s_=self.style(_c, "_"),
                sh2=self.style(_c, "h2"),
                ssec=self.style(_c, "section"),
            )
        else:
            _f = lambda s: s.format(s_="", sh2="", ssec="")
        body = map(_f, body)
        return "\n".join(body)

    def _table(self, section, rows):
        if self._email:
            inline = {k: self.style("table", k) for k in self.styles["table"]}
        else:
            inline = dict.fromkeys(self.styles["table"], "")
        subsets, _ = self.result_subsets(rows)
        tables = []
        for subset in subsets:
            tables.append("<table{table}>".format(**inline))
            cols = self.ordered_cols(subset, section)
            # Format the table.
            tables.extend(
                ["<tr{tr1}>".format(**inline)] + ["<th{th}>{c}</th>".format(c=c, **inline) for c in cols] + ["</tr>"]
            )
            self.sort_rows(rows, section)
            for i, r in enumerate(rows):
                tr = "{{tr_{}}}".format(("even", "odd")[i % 2])
                if tuple(sorted(r.keys())) != subset:
                    continue
                if self._url is not None:
                    r[cols[0]] = "<a href='{p}{v}'>{v}</a>".format(p=self._url, v=r[cols[0]])
                tables.extend(
                    [f"<tr{tr}>".format(**inline)]
                    + ["<td{td}>{d}</td>".format(d=r[c], **inline) for c in cols]
                    + ["</tr>"]
                )
            tables.append("</table>")
        return tables


class DiffTextFormatter(DiffFormatter):
    """Format a plain-text diff report."""

    def format(self, result):
        """Generate plain text report.

        :return: Report body
        :rtype: str
        """
        m = self.meta
        lines = [
            "-" * len(self.TITLE),
            self.TITLE,
            "-" * len(self.TITLE),
            "Compared: {db1} <-> {db2}".format(**m),
            "Filter: {filter}".format(**m),
            "Run time: {start_time} -- {end_time} ({elapsed:.1f} sec)".format(**m),
            "",
        ]
        for section in result.keys():
            lines.append("* " + section.title())
            indent = " " * 4
            if len(result[section]) == 0:
                lines.append(f"{indent}EMPTY")
            else:
                keyset, maxwid = self.result_subsets(result[section])
                for columns in keyset:
                    ocol = self.ordered_cols(columns, section)
                    mw = maxwid[columns]
                    mw_i = [columns.index(c) for c in ocol]  # reorder indexes
                    fmt = "  ".join([f"{{:{mw[i]:d}s}}" for i in mw_i])
                    lines.append("")
                    lines.append(indent + fmt.format(*ocol))
                    lines.append(indent + "-_" * (sum(mw) / 2 + len(columns)))
                    rows = result[section]
                    self.sort_rows(rows, section)
                    for r in rows:
                        key = tuple(sorted(r.keys()))
                        if key == columns:
                            values = [str(r[k]) for k in ocol]
                            lines.append(indent + fmt.format(*values))
        return "\n".join(lines)

    def _record(self, rec):
        fields = [f"{k}: {v}" for k, v in rec.items()]
        return "{" + ", ".join(fields) + "}"
