#!/usr/bin/env python3
"""The leak lint (ARCHITECTURE 9.6; WP4 decisions X01 to X47 and Y01 to Y09).

leak_lint.py keeps internal details, and other clients' details, out of anything the plugin writes into monday.
It reads a draft, a .docx or a payload, checks it against the shipped list, the user's local list and settings,
and the client record's own figures, quotes, internal text and exclusions, and reports. It never edits a file,
it writes nothing (the index apart, which `index` alone will write) and it never calls monday. Every command
prints one JSON object, {"ok", "command", "verdict", ...}, and exits 0 (clean), 1 (blocked), 2 (warnings or
cautions only) or 3 (could not run, which every caller treats as a stop). Standard library only, Python 3.9 and
later, the same on Windows and macOS.

This build runs `scan` and `payload`. `blueprint`, `wall`, `terms` and `index` are in the parser and answer
exit 3, "not built yet". The cross-client wall inside `scan` and `payload` is not built either: a run in a home
that holds another client record, or an index, stops with exit 3, so nothing passes on a path that is not built.
"""
import sys
sys.dont_write_bytecode = True  # no cache beside the scripts (G49), set before mmb_common is imported


def python_too_old(version=None):
    """The envelope for an interpreter older than 3.9, or None (L206)."""
    found = tuple(version or sys.version_info[:2])[:2]
    if found >= (3, 9):
        return None
    return ('{"ok": false, "command": null, "verdict": "could-not-run", "error": {"file": "leak_lint.py", '
            '"field": "python", "problem": "Python %d.%d", "expected": "Python 3.9 or later"}}\n' % found)


if python_too_old():
    sys.stdout.write(python_too_old())
    sys.exit(3)

import argparse, bisect, hashlib, io, json, os, re, unicodedata, zipfile  # noqa: E401,E402
import xml.etree.ElementTree as ET  # noqa: E402
from datetime import date  # noqa: E402
from fractions import Fraction  # noqa: E402
from pathlib import Path, PurePosixPath  # noqa: E402
import mmb_common as mc  # noqa: E402

# pinned: leak
MARKERS = ("[Q]", "[Q?]", "[Q/side]", "[Q/recon]", "[Q/doc]", "[X]", "[E]", "[I]", "[A]")
KINDS = ("workspace", "folder", "board", "group", "column", "view", "form", "subitems", "doc", "dashboard", "widget",
         "automation", "portfolio", "project", "workflow", "agent", "ai_column", "vibe_app", "sequence", "webhook",
         "item_batch", "publication", "activation", "generic")
FAMILIES = ("name", "description", "label", "seed", "markdown", "request_text", "role", "role_description", "goal",
            "plan", "user_prompt", "knowledge_name", "prompt", "app_name", "step_text", "recipient", "url")
KIND_FAMILIES = ((("agent",), ("name", "role", "role_description", "goal", "plan", "user_prompt", "knowledge_name")),
                 (("vibe_app",), ("prompt", "app_name")),
                 (("ai_column",), ("name", "prompt")),
                 (("workflow",), ("name", "description", "step_text")),
                 (("sequence",), ("name", "step_text", "recipient")),
                 (("webhook",), ("url",)),
                 (("automation",), ("name", "request_text")),
                 (("item_batch",), ("name", "seed")),
                 (("doc",), ("name", "markdown")),
                 (("workspace", "folder", "board", "group", "column", "view", "form", "subitems", "dashboard", "widget",
                   "portfolio", "project", "publication", "activation"), ("name", "description", "label")),
                 (("generic",), FAMILIES))
BLOCK_MARKS = ("<!-- client-safe:start -->", "<!-- client-safe:end -->", "<!-- glossary:start -->",
               "<!-- glossary:end -->")
HEADINGS = ("## Conflicts", "## Exclusions", "## Allowlist")
ROW_KEYS = ("kind", "added", "by", "source", "ok", "date", "class")
EXCLUSION_KINDS = ("name", "term", "figure")
INDEX_FIELDS = ("clients-index/1", "schema", "hash", "normalisation", "entries", "updated", "names", "phonetic",
                "terms", "figures")
INDEX_FORMS = ("sha256-128", "wall/1")
SEVERITIES = ("block", "warn", "caution")
VERDICTS = ("clean", "warnings", "blocked", "could-not-run")
MODES = ("full", "summary", "client-safe-block", "blueprint")
RULES = ("term", "phonetic", "seller-account", "figure", "split-figure", "copied-run", "quote", "exclusion", "wall",
         "credential", "internal-note", "paraphrase", "tool-categories", "number", "record-number", "allowlist")
WALL_CLASSES = ("name", "term", "figure", "slug")
CLEARABLE = ("method", "internal-vocabulary", "sales-framing", "assessment", "emotional", "health-identity",
             "departure", "colleague-remark", "personal-life")
COUNTED_PREFIX = "tool-category-"
LOCAL_CLASS = "local"
# end pinned

# pinned: common-words
# About a thousand ordinary English words and about sixty monday and work words, lower case, with the
# apostrophes of contractions removed as the tokeniser removes them (X19). A six-word stretch counts toward
# the copied-run rule only when RUN_MIN_DISTINCT of its words are outside this list; a number always is.
COMMON_WORDS = frozenset("""
a able about above across act action actual actually add added adding after afternoon afterwards again against
age ago agree agreed ahead air all allow allowed almost alone along already alright also although always am among
amount an and another answer answered any anybody anyone anything anyway anywhere apart appear apply applied april
are area areas arent arm around arrive arrived as ask asked asking at august available away back bad bag ball bank
bar base basic basis be became because become becomes been before began begin beginning behind being believe below
beside best better between beyond big bit black blue body book books both bottom bought box boy break bright bring
brings brother brought brown build builds built busy but buy by call called calling calls came can cannot cant car
card care careful carry carried case cases catch caught cause certain certainly chance change changed changes check
checked checking child children choice choose chose city class clear clearly close closed club cold colour color
come comes coming common company complete completely condition consider considered continue continued corner
correct could couldnt country couple course court cover covered create created cup current currently cut cuts
daily dark data date dates day days dead deal dear december decide decided decision deep degree describe design
detail details develop did didnt different difficult direct direction do does doesnt doing done dont door doors
down draw drew drink drive drop dropped due during each earlier early earth easily easy eat effect effort eight
either else elsewhere empty end ended ending ends energy enough entire equal even evening event events ever every
everybody everyone everything everywhere exact exactly example except expect expected experience explain explained
extra eye eyes face fact fair fall family far fast father february feel feeling feels fell felt few field fifth
figure fill filled final finally find finds fine finish finished first five fix fixed floor follow followed
following food foot for force form former forward found four fourth free friday friend friends from front full
fun further future game garden gave general get gets getting girl give given gives giving glad glass go goal goes
going gone good got gotten great green ground group grow growth guess had hadnt half hall hand hands happen
happened happens happy hard has hasnt have havent having he head health hear heard heart heavy held hello help
helped helps hence her here hers herself hes high him himself his history hold holds home hope hoped hour hours
house how however huge hundred i id idea ideas if ill im important in include included includes including indeed
information inside instead interest interesting into is isnt issue issues it item items itll its itself ive january
job jobs july june just keep keeps kept key kind knew know known knows land language large last late later law learn
learned least leave leaves led left less let lets level life light like liked likely likes line lines list listen
little live lived local long look looked looking looks lose losing lost lot lots love low made main major make makes
making man many march matter may maybe me mean means meant meanwhile meet meeting meetings meets member men message
met method middle might million mind mine minute minutes miss moment monday money month monthly months more moreover
morning most mostly mother move moved moves much must my myself name names nature near nearly necessary need needed
needs neither never new news next nice night nine no nobody none nor normal not note notes nothing november now
nowhere number numbers october of off offer offered office often oh ok okay old on once one only onto open opened
opens or order orders other others otherwise our ours ourselves out outside over own page pages paper part particular
parts party pass passed past pay people per perfect perhaps period person phone pick picked picture piece place
places plan planned plans play played please point points policy position possible power practice prefer prepare
prepared present pretty price probably problem problems process product program project proper provide provided
public pull push put puts question questions quick quickly quiet quite rather reach read reading reads ready real
really reason receive received recent recently record records red remember remove removed reply report reported
rest result results return right road role room round rule rules run running runs safe said same saturday save
saved saw say saying says school second see seeing seem seemed seems seen sell send sends sense sent september
serious set sets seven several shall shape she shes short should shouldnt show showed shown shows side sign similar
simple since single sit six size skill slow small so soft some somebody someone something sometime sometimes
somewhere soon sort space speak special spend spent staff stage stand start started starts state stay stayed step
steps still stop stopped story street strong student study subject such suggest suggested sunday support sure
sweet system table take taken takes taking talk talked talking tall task team tell telling tells ten term terms test
than thank thanks that thats the their theirs them themselves then there thereafter therefore theres these they
theyd theyll theyre theyve thing things think thinking thinks third this those though thought thousand three
through throughout thursday thus time times to today together told tomorrow tonight too took top total toward
towards town tree tried tries trip true truth try trying tuesday turn turned two type under understand unit unless
until up update upon us use used uses using usual usually value various very via view voice wait waiting walk wall
want wanted wants war warm was wasnt watch water way ways we weak wed wednesday week weekend weekly weeks well went
were werent weve what whatever whats when whenever where wherever whether which while white who whoever whole whom
whose why wide wife will window with within without wont word words work worked working works world would wouldnt
write writes writing written wrong wrote year yearly years yellow yes yesterday yet you youd youll young your youre
yours yourself yourselves youve
board boards subitem subitems status statuses groups column columns owner owners timeline timelines dashboard
dashboards views form forms automation automations workflow workflows updates task tasks project projects team
teams client clients customer customers reports request requests file files doc docs document documents priority
priorities stages deadline deadlines workspace workspaces folder folders label labels tag tags assign assigned
assignee approval approvals approve approved review reviews comment comments link links template templates track
tracking schedule schedules email emails call contact contacts sheet sheets quote quotes service crm dev vibe
management manager admin user users account accounts
""".split())
RUN_MIN_DISTINCT = 2
# end pinned

# pinned: stop-words
# The stop list of X26 beside the common words: monday's product words, titles, role acronyms and common acronyms.
# The proper-noun test of the tool-category assertion never counts these, and the wall's name harvest (part 2) drops
# them; the shipped plugin, assistant, method and marker rows join it at run time.
PRODUCT_WORDS = frozenset(("monday", "work", "management", "crm", "service", "dev", "vibe"))
STOP_WORDS = frozenset(("mr", "mrs", "ms", "mx", "dr", "prof", "sir", "ceo", "cfo", "coo", "cto", "vp", "hr", "it",
                        "pm", "pms", "qa", "crm", "erp", "sop", "api", "eta", "pdf", "kpi", "roi", "sla", "faq", "uk",
                        "us", "usa", "eu", "id", "ok", "am", "tv", "bi"))
# end pinned

# pinned: paraphrase-cues
# The six cue groups of X06. A sentence blocks when it holds a cue and a person reference: a capitalised token not
# at the sentence start and not a common word, or one of the role words. Cues are matched as normalised words.
PARAPHRASE_CUES = (
    ("assessment", ("decision maker", "the real decision maker", "approver", "gatekeeper", "blocker", "champion",
                    "skeptic", "sceptic", "veto", "influencer", "holdout", "long pole", "single point of failure",
                    "weak link", "a risk", "ally", "hostile", "resistant", "on board", "will kill it", "can kill it",
                    "signs off", "not technical", "calls the shots", "pushover", "dead weight", "deadweight",
                    "bottleneck", "troublemaker", "out of her depth", "out of his depth", "out of their depth",
                    "cant be trusted", "not senior enough")),
    ("emotional", ("burnt out", "burned out", "burnout", "stressed", "stressed out", "crying", "cried", "in tears",
                   "upset", "embarrassed", "embarrassing", "humiliated", "ashamed", "furious", "angry", "scared",
                   "frightened", "anxious", "anxiety", "keeps me up", "keeps her up", "keeps him up", "lose sleep",
                   "losing sleep", "devastated", "heartbroken", "overwhelmed", "exhausted", "miserable", "depressed",
                   "panicking", "breaking point", "fed up")),
    ("health-identity", ("hospital", "hospitalised", "hospitalized", "surgery", "illness", "sick", "sick leave",
                         "sick note", "medical leave", "maternity leave", "paternity leave", "diagnosis", "diagnosed",
                         "cancer", "pregnant", "pregnancy", "injury", "injured", "therapy", "therapist", "disability",
                         "disabled", "mental health", "rehab", "nationality", "citizenship", "visa", "immigrant",
                         "immigration", "accent", "ethnicity", "religion", "religious", "american", "british",
                         "english", "scottish", "welsh", "irish", "german", "spanish", "italian", "portuguese",
                         "belgian", "swiss", "austrian", "czech", "russian", "ukrainian", "romanian", "bulgarian",
                         "greek", "turkish", "indian", "pakistani", "bangladeshi", "chinese", "japanese", "korean",
                         "vietnamese", "filipino", "thai", "indonesian", "malaysian", "australian", "canadian",
                         "mexican", "brazilian", "argentinian", "colombian", "nigerian", "kenyan", "ghanaian",
                         "ethiopian", "somali", "egyptian", "moroccan", "lebanese", "iranian", "iraqi", "syrian",
                         "afghan", "israeli", "palestinian", "jamaican")),
    ("departure", ("leave the business", "leaving the business", "left the business", "leave the company",
                   "leaving the company", "left the company", "quit", "quits", "quitting", "resign", "resigns",
                   "resigning", "resignation", "retire", "retires", "retiring", "retirement", "let go", "fired",
                   "laid off", "made redundant", "redundancy", "poached", "moving on", "handing in notice",
                   "hand in notice", "notice period", "walked out")),
    ("colleague-remark", ("hates", "hate", "cant stand", "never answers", "doesnt answer", "wont answer", "ignores",
                          "useless", "lazy", "clueless", "hopeless", "disgrace", "nightmare", "menace", "careless",
                          "sloppy", "unreliable", "rude", "will kill me", "buried with", "incompetent", "a joke",
                          "idiot", "moron", "drives me mad", "drives me crazy", "cant be bothered", "two faced",
                          "backstabbing", "toxic", "difficult to work with")),
    ("personal-life", ("vacation", "holiday", "holidays", "birthday", "golf", "hangover", "hungover", "kids",
                       "children", "girlfriend", "boyfriend", "divorce", "divorced", "wedding", "honeymoon",
                       "date night", "dating")))
ROLE_WORDS = ("boss", "manager", "director", "owner", "founder", "partner", "ceo", "cfo", "coo", "cto", "vp",
              "president", "chairman", "chair", "controller", "colleague", "coworker", "co worker", "assistant",
              "receptionist", "supervisor", "lead", "mother", "father", "mum", "mom", "dad", "wife", "husband", "son",
              "daughter", "brother", "sister")
PRONOUNS = frozenset(("i", "me", "my", "mine", "he", "him", "his", "she", "her", "hers", "they", "them", "their",
                      "theirs", "we", "us", "our", "ours", "you", "your", "yours", "it", "its"))
# end pinned

# pinned: internal-vocabulary
# The plugin's own words the shipped method class lacks (X06); a term finding of this class, clearable as vocabulary.
INTERNAL_VOCABULARY = ("composite block", "candidate segment", "own side stretch", "swallowed assent",
                       "boundary artifact", "shred index", "talk share", "delivery notes", "alias table",
                       "intake report", "type header", "proposed and displaced", "compound show")
# end pinned

# pinned: sales-framing
# Backlog framed as a sale (X06); a term finding of this class, clearable as vocabulary.
SALES_FRAMING = ("upsell", "up sell", "upselling", "upsell opportunity", "cross sell", "cross selling",
                 "land and expand", "expansion opportunity", "closing tactic", "closing tactics")
# end pinned

# pinned: cost-cues
# A number of the record is a cost figure when its sentence holds one of these, a currency sign or a currency code
# (X25). Rate suffixes let a payload figure of 10 to 999 block without a cost word.
COST_CUES = ("cost", "costs", "costed", "costing", "price", "prices", "priced", "pricing", "rate", "rates", "loaded",
             "salary", "salaries", "wage", "wages", "pay", "pays", "paid", "paying", "fee", "fees", "budget",
             "budgets", "spend", "spends", "spending", "spent", "threshold", "thresholds", "signs", "signature",
             "signatures", "sign off", "invoice", "invoices", "invoiced", "billed", "billing", "bill", "bills",
             "revenue", "revenues", "margin", "margins", "profit", "profits", "loss", "losses", "lost", "write off",
             "write offs", "written off", "credit", "credits", "refund", "refunds", "penalty", "penalties", "overrun",
             "overruns", "saving", "savings", "worth", "value", "values", "contract", "contracts", "renewal",
             "renewals", "discount", "discounts", "payback", "bleed", "upside", "hourly", "per hour", "an hour",
             "day rate", "day rates", "charge", "charges", "charged", "dollar", "dollars", "buck", "bucks", "pound",
             "pounds", "euro", "euros", "grand")
CURRENCY_CODES = ("usd", "gbp", "eur", "cad", "aud", "nzd", "chf")
RATE_SUFFIX = r"[ \t]?(?:/[ \t]?h(?:r|our)?\b|an[ \t]+hour\b|per[ \t]+hour\b|an[ \t]+hr\b)"
# end pinned

# pinned: confusables
# Cyrillic and Greek letters that look like Latin ones, folded before case folding (X28); dashes fold to a hyphen.
CONFUSABLES = {"а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j", "ѕ": "s",
               "к": "k", "м": "m", "н": "h", "т": "t", "в": "b",
               "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T",
               "У": "Y", "Х": "X", "І": "I", "Ј": "J", "Ѕ": "S",
               "α": "a", "ε": "e", "ι": "i", "κ": "k", "ν": "v", "ο": "o", "ρ": "p", "τ": "t", "υ": "u", "χ": "x",
               "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O",
               "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X",
               "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-",
               "−": "-", "⁄": "/"}
NARROW_SPACES = frozenset((" ", " ", " "))  # kept as one narrow space: a thousands separator
# end pinned

# pinned: credential-shapes
# The six shapes of X15 (with Y04's spaces around the separator). Shapes 3 and 4 run on percent-decoded text too;
# shape 6 runs outside links only. A credential finding is never cleared.
CREDENTIAL_SHAPES = (
    ("authorisation header", r"\b(?:bearer|basic|token)\s+[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE),
    ("secret pair", r"\b(?:password|passwd|pwd|pass|secret|token|api_key|api-key|apikey|access_key|access-key|"
                    r"client_secret|auth)[*_\"'“”‘’ \t]*[:=][ \t]*[\"'“”‘’]?[^\s\"'“”‘’]{4,}", re.IGNORECASE),
    ("url with user info", r"[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@", re.IGNORECASE),
    ("url token parameter", r"[?&](?:token|key|api_key|apikey|access_token|auth|secret|signature|sig|password|pwd|"
                            r"code)=[^&\s#]{6,}", re.IGNORECASE),
    ("json web token", r"\beyJ[A-Za-z0-9_-]{7,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", 0),
    ("access key id", r"\bAKIA[A-Z0-9]{16}\b", 0),
    ("prefixed key", r"\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{16,}", 0),
    ("repository token", r"\bgh[pousr]_[A-Za-z0-9]{36,}", 0),
    ("chat platform token", r"\bxox[abprs]-[A-Za-z0-9-]+", 0),
    ("private key", r"-----BEGIN[A-Z ]*PRIVATE KEY-----", 0))
LONG_SECRET = r"(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/=_-]{32,}(?![A-Za-z0-9+/=_-])"
# end pinned

# pinned: internal-notes
# The marks of the record's own internal files (X40, Y07); an internal-note finding is never cleared.
INTERNAL_NOTE_PHRASES = ("internal: never client-facing", "never client-facing", "internal only", "not for the client",
                         "note to self")
FRONT_MATTER_LINE = r"^[a-z][a-z0-9_-]*:[ \t]*[\"“”][^\"“”\n]*[\"“”]"
SPEAKER_LABEL = r"\bspeaker[ \t]*\d+\b"
# end pinned

# pinned: structural-id-keys
# Y08: a digit-only value directly under one of these keys is a monday id, not text. tests/unit/test_leak_fixture.py
# holds a copy, and a unit test keeps the two equal.
STRUCTURAL_ID_KEYS = frozenset("""
id ids account_id workspace_id workspace_ids workspaceId workspaceIds folder_id folder_ids folderId board_id board_ids
boardId boardIds group_id groupId item_id item_ids itemId itemIds parent_id parentId parent_item_id doc_id docId
object_id objectId view_id viewId dashboard_id dashboardId widget_id widgetId automation_id automationId workflow_id
workflowId agent_id agentId app_id appId user_id user_ids userId userIds team_id team_ids teamId teamIds owner_ids
subscriber_ids
""".split())
# end pinned

PLUGIN = Path(__file__).resolve().parent.parent
KEYS = ("file", "field", "problem", "expected")
WHOLE = mc.WHOLE_FILE
MB = 1024 * 1024
TEXT_LIMIT, PAYLOAD_LIMIT, DEPTH_LIMIT = 20 * MB, 20 * MB, 64
DOCX_MEMBER_LIMIT, DOCX_TOTAL_LIMIT, DOCX_RATIO, DOCX_RATIO_FLOOR = 50 * MB, 200 * MB, 100, 1 * MB
LINE_WINDOW, LINE_OVERLAP = 10000, 200
RUN_WORDS, NEAR_WORDS, QUOTE_WORDS = 6, 8, 8
MATCH_CUT = 80
TEXT_EXT, SCAN_EXT, SYSTEM_FILES = (".md", ".txt", ".docx"), (".md", ".txt", ".docx", ".json"), \
    frozenset((".ds_store", "thumbs.db", "desktop.ini"))
SHIPPED_NAME, SETTINGS_NAME, LOCAL_NAME = "<plugin>/shared/leak-terms.txt", "<home>/local/settings.json", \
    "<home>/local/leak-terms.txt"
ID_ROW = r"(?<![\w/=?&#.-])\d{8,}(?![\w-])"  # the eight-digit monday id row of id-patterns, the one that skips links
ID_WIDE = re.compile(r"(?<![^\W_])\d{8,}(?![^\W_])")  # the same row beside any mark once real links are masked (Z03)
CLASS_NAME = re.compile(r"[A-Za-z0-9-]+")
NESTED = re.compile(r"\((?:[^()\\]|\\.)*(?:[*+]|\{\d*,\d*\})(?:[^()\\]|\\.)*\)(?:[*+]|\{\d*,?\d*\})")
GAP = r"[\s,.\-_/|·]+"
LEGAL_SUFFIXES = frozenset(("inc", "incorporated", "llc", "ltd", "limited", "plc", "gmbh", "corp", "corporation", "co",
                            "company", "lp", "llp", "sa", "ag", "bv", "nv", "pty", "pte", "srl", "oy", "ab"))  # X28 step 6
WORDCHAR = r"[^\W_]"
TOKEN = re.compile(r"[^\W_]+(?:['’][^\W_]+)*")
POSSESSIVE = re.compile(r"['’]s$")
SENTENCE_END = re.compile(r"(?:\.|!|\?)(?=\s|$)|\n")
QUOTE_SPANS = re.compile(r"(?:\"|“|”)([^\"“”\n]+)(?:\"|“|”)")
LOCATION = re.compile(r"@\d{2}:\d{2}:\d{2}\b|\bcues? \d+(?:-\d+)?\b|\bL\d{2,4}(?:-\d{1,4})?\b", re.IGNORECASE)
LINKS = (re.compile(r"!?\[[^\]\n]*\]\(\s*<?([^)\s>]+)"),
         re.compile(r"\b(?:href|src)\s*=\s*(?:\"|')([^\"']*)(?:\"|')", re.IGNORECASE),
         re.compile(r"<((?:https?://|mailto:)[^>\s]+)>", re.IGNORECASE),
         re.compile(r"(?<![\w/])((?:https?://|mailto:)[^\s)\]>]+)", re.IGNORECASE))
PERCENT = re.compile(r"(?:%[0-9A-Fa-f]{2})+")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
SNAPSHOT = re.compile(r'^schema:[ \t]*"document-summary/1"[ \t]*$')
SIMPLE_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
STRUCTURAL_VALUE = re.compile(r"[1-9][0-9]*")


# The frame (a copy of ledger.py's, nod 2 and W91): the envelope, the refusal helper, the parser.

class Usage(Exception):
    """A usage error: exit 3 with the JSON envelope, never argparse's own exit 2 (G10)."""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Usage(message)


def emit(data):
    """Print one JSON object as UTF-8 with LF: the same bytes on every system."""
    text = mc.json_text(data)
    sys.stdout.flush()
    raw = getattr(sys.stdout, "buffer", None)
    if raw is None:
        sys.stdout.write(text)
    else:
        raw.write(text.encode("utf-8"))
        raw.flush()


def cannot(file, field, problem, expected):
    """The could-not-run stop (exit 3), one (file, field, problem, expected) finding."""
    return mc.CannotRun((file, field, problem, expected))


def read_bytes(path):
    """Every file the lint reads goes through here, so a failed read is one place (L207)."""
    with open(str(path), "rb") as handle:
        return handle.read()


# Text: folding with a map back to the original, tokens, sentences and paragraphs (X24, X28).

class Variant:
    """A copy of a text with, for each of its characters, the offset of the original character it came from."""
    __slots__ = ("text", "offsets")

    def __init__(self, text, offsets):
        self.text, self.offsets = text, offsets

    def span(self, start, end):
        """The original (start, end) of this copy's [start, end)."""
        if not self.offsets:
            return 0, 0
        start = min(start, len(self.offsets) - 1)
        first = self.offsets[start]
        last = self.offsets[max(start, min(end, len(self.offsets)) - 1)] + 1
        return first, max(first, last)


def plain(text, base=0):
    return Variant(text, list(range(base, base + len(text))))


def fold(text, offsets=None):
    """X28 steps 1 to 4: format characters removed, NFKC, look-alikes folded, case folded, diacritics dropped."""
    out, where = [], []
    for index, char in enumerate(text):
        origin = offsets[index] if offsets is not None else index
        if char < "\x80":
            out.append(char.lower())
            where.append(origin)
            continue
        if char in NARROW_SPACES:
            out.append(" ")
            where.append(origin)
            continue
        if unicodedata.category(char) == "Cf":
            continue
        for part in unicodedata.normalize("NFKC", char):
            part = CONFUSABLES.get(part, part)
            for piece in unicodedata.normalize("NFD", part.casefold()):
                if unicodedata.category(piece) != "Mn":
                    out.append(piece)
                    where.append(origin)
    return Variant("".join(out), where)


def fold_variant(variant):
    folded = fold(variant.text)
    return Variant(folded.text, [variant.offsets[i] for i in folded.offsets])


def fold_text(text):
    return fold(text).text


def percent_decode(variant):
    """A copy with every run of %XX escapes decoded as UTF-8 (X03), mapped back to the original."""
    out, where, last = [], [], 0
    for match in PERCENT.finditer(variant.text):
        out.append(variant.text[last:match.start()])
        where.extend(variant.offsets[last:match.start()])
        decoded = bytes(int(match.group()[i + 1:i + 3], 16) for i in range(0, len(match.group()), 3))
        piece = decoded.decode("utf-8", errors="replace")
        out.append(piece)
        where.extend([variant.offsets[match.start()]] * len(piece))
        last = match.end()
    out.append(variant.text[last:])
    where.extend(variant.offsets[last:])
    return Variant("".join(out), where)


def slashed(variant):
    return Variant(variant.text.replace("\\", "/"), variant.offsets)


def words_of(text):
    """The normalised words of a text (X24): folded, possessive dropped, apostrophes removed."""
    found = []
    for match in TOKEN.finditer(fold_text(text)):
        word = POSSESSIVE.sub("", match.group()) if len(match.group()) > 2 else match.group()
        word = word.replace("'", "").replace("’", "")
        if word:
            found.append(word)
    return found


def normal_form(text):
    """The spaced normal form X28 compares: the words joined by one space."""
    return " ".join(words_of(text))


class Token:
    __slots__ = ("word", "fstart", "fend", "start", "end", "cap", "upper", "sentence", "paragraph", "first")

    def __init__(self, word, fstart, fend, start, end, cap, upper):
        self.word, self.fstart, self.fend, self.start, self.end = word, fstart, fend, start, end
        self.cap, self.upper, self.sentence, self.paragraph, self.first = cap, upper, 0, 0, False


def sentence_spans(text):
    """A sentence ends at . ! or ? before whitespace or the end, and at every line break (X12)."""
    spans, start = [], 0
    for match in SENTENCE_END.finditer(text):
        spans.append((start, match.end()))
        start = match.end()
    if start < len(text):
        spans.append((start, len(text)))
    return spans


def paragraph_spans(text):
    """Blocks of lines between blank lines; a heading is a paragraph of its own (X12)."""
    spans, start, end, position = [], None, None, 0
    for line in text.split("\n"):
        line_start, line_end = position, position + len(line)
        position = line_end + 1
        if not line.strip() or line.lstrip().startswith("#"):
            if start is not None:
                spans.append((start, end))
                start = None
            if line.strip():
                spans.append((line_start, line_end))
            continue
        if start is None:
            start = line_start
        end = line_end
    if start is not None:
        spans.append((start, end))
    return spans


def tokenise(original, folded):
    """Tokens of a folded copy, each with its original span, its case and its sentence and paragraph."""
    sentences = sentence_spans(folded.text)
    paragraphs = paragraph_spans(folded.text)
    s_starts, p_starts = [s for s, _ in sentences], [s for s, _ in paragraphs]
    tokens, last_sentence = [], None
    for match in TOKEN.finditer(folded.text):
        raw = match.group()
        word = POSSESSIVE.sub("", raw) if len(raw) > 2 else raw
        word = word.replace("'", "").replace("’", "")
        if not word:
            continue
        start, end = folded.span(match.start(), match.end())
        shown = original[start:end]
        token = Token(word, match.start(), match.end(), start, end, shown[:1].isupper(),
                      shown.isupper() and any(c.isalpha() for c in shown))
        token.sentence = max(0, bisect.bisect_right(s_starts, match.start()) - 1)
        token.paragraph = max(0, bisect.bisect_right(p_starts, match.start()) - 1)
        token.first = token.sentence != last_sentence
        last_sentence = token.sentence
        tokens.append(token)
    return tokens


def link_spans(text):
    """The targets of Markdown links and images, href and src values, autolinks and bare URLs (X34)."""
    spans = []
    for pattern in LINKS:
        for match in pattern.finditer(text):
            spans.append((match.start(1), match.end(1)))
    return sorted(spans)


def inside(spans, start, end):
    return any(s <= start and end <= e for s, e in spans)


def mask(text, spans):
    if not spans:
        return text
    chars = list(text)
    for start, end in spans:
        for i in range(start, end):
            chars[i] = " "
    return "".join(chars)


def literal_regex(term, tokenised=False, fused=False):
    """A literal row as a pattern on folded text: boundaries of LT:18, the gaps of X32, and the fused form."""
    folded = fold_text(term)
    words = words_of(term) if tokenised else folded.split()
    if not words:
        return None
    apostrophe = "'" in folded or "’" in folded

    def piece(word):
        if tokenised and apostrophe:
            return "['’]?".join(re.escape(c) for c in word)
        return re.escape(word)

    forms = [words]
    if tokenised:
        bare = list(words)
        while len(bare) > 1 and bare[-1] in LEGAL_SUFFIXES:
            bare.pop()
        if bare != words:
            forms.append(bare)
    alternatives = []
    for form in forms:
        alternatives.append(GAP.join(piece(word) for word in form))
        if fused and len(form) > 1:
            alternatives.append(re.escape("".join(form)))
    return re.compile(r"(?<!%s)(?:%s)(?!%s)" % (WORDCHAR, "|".join(alternatives), WORDCHAR))


def cut(text):
    text = " ".join(text.split())
    return text if len(text) <= MATCH_CUT else text[:MATCH_CUT - 1] + "…"


# The phonetic key and the edit distance (X32, Y09).

VOWELS = frozenset("aeiou")
PHONE_MAP = {"b": "P", "p": "P", "f": "F", "k": "K", "g": "K", "j": "J", "s": "S", "t": "T", "d": "T", "l": "L",
             "m": "M", "n": "M", "r": "R", "X": "X", "0": "0"}
FIRST_KEEP = {"w": "W", "h": "H", "y": "Y"}


def phonetic_key(word):
    """The key of one word: X32's rewrites, the symbol map, the first letter kept, runs collapsed."""
    w = "".join(c for c in fold_text(word) if "a" <= c <= "z")
    if not w:
        return ""
    for head, new in (("kn", "n"), ("gn", "n"), ("pn", "n"), ("wr", "r"), ("ps", "s"), ("wh", "w")):
        if w.startswith(head):
            w = new + w[2:]
            break
    else:
        if w.startswith("x"):
            w = "s" + w[1:]
    phones, i, n = [], 0, len(w)
    while i < n:
        c, two, three = w[i], w[i:i + 2], w[i:i + 3]
        after = w[i + 1] if i + 1 < n else ""
        if two == "ph":
            phones.append("f"); i += 2; continue  # noqa: E702
        if two == "ck":
            phones.append("k"); i += 2; continue  # noqa: E702
        if three == "sch":
            phones.extend("sk"); i += 3; continue  # noqa: E702
        if three == "tch":
            phones.append("X"); i += 3; continue  # noqa: E702
        if two in ("ch", "sh"):
            phones.append("X"); i += 2; continue  # noqa: E702
        if two == "th":
            phones.append("0"); i += 2; continue  # noqa: E702
        if two == "dg":
            phones.append("j"); i += 2; continue  # noqa: E702
        if two == "qu":
            phones.extend("kw"); i += 2; continue  # noqa: E702
        if c == "x":
            phones.extend("ks"); i += 1; continue  # noqa: E702
        if two == "gh" and (i + 2 >= n or w[i + 2] not in VOWELS):
            i += 2
            continue
        if c == "c":
            phones.append("s" if after and after in "eiy" else "k")
        elif c == "g":
            phones.append("j" if after and after in "eiy" else "g")
        else:
            phones.append({"q": "k", "z": "s", "v": "f"}.get(c, c))
        i += 1
    out = []
    for index, phone in enumerate(phones):
        if index == 0 and (phone in VOWELS or phone in FIRST_KEEP):
            out.append("A" if phone in VOWELS else FIRST_KEEP[phone])
        elif phone in PHONE_MAP:
            out.append(PHONE_MAP[phone])
    key = []
    for symbol in out:
        if not key or key[-1] != symbol:
            key.append(symbol)
    return "".join(key)


def letters(word):
    return "".join(c for c in fold_text(word) if "a" <= c <= "z")


def edit_distance(a, b, limit):
    """Damerau-Levenshtein distance (adjacent transpositions), or limit + 1 once it is past the limit."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    previous2, previous = None, list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        current = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            current[j] = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost)
            if previous2 is not None and i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                current[j] = min(current[j], previous2[j - 2] + 1)
        if min(current) > limit:
            return limit + 1
        previous2, previous = previous, current
    return previous[len(b)]


class PhoneticSource:
    """One source of the phonetic rule: its words, keys and letters, and its whitelist rows."""

    def __init__(self, cls, term, origin, whitelist):
        self.cls, self.term, self.origin, self.whitelist = cls, term, origin, whitelist
        self.words = words_of(term)
        keys = [phonetic_key(w) for w in self.words]
        self.letters = "".join(letters(w) for w in self.words)
        self.keys = {" ".join(keys), "".join(keys), phonetic_key(self.letters)} - {""}
        size = len(self.letters)
        self.limit = 0 if size < 5 else (1 if size <= 7 else 2)


# The run: the record, the home, every input read with its hash, and the findings (X16, X41).

class Run:
    """One command's state. Inputs are recorded as they are read, so the output names every byte judged."""

    def __init__(self, command, args):
        self.command, self.args = command, args
        self.root = self.home = None
        self.inputs, self.findings, self.error = {}, [], None
        self.mode, self.strand, self.args_digest = None, None, None
        self.lists = self.sets = None
        self.allowlists, self.wall_checked = {}, False
        self.spans = bool(getattr(args, "spans", False))
        self.order = 0

    def locate(self):
        """The record as record.py and ledger.py locate it (W91): --record, else the current folder."""
        root = Path(self.args.record) if self.args.record else Path.cwd()
        if not (root / "CLIENT.md").is_file():
            raise cannot("CLIENT.md", "record", "no CLIENT.md in the folder %s" % root.name,
                         "a client folder holding CLIENT.md, or --record <folder>")
        self.root, self.home = root.resolve(), mc.home()

    def name(self, path):
        """A record-relative POSIX name, or <home>/... for a file under the home outside the record."""
        resolved = Path(os.path.abspath(str(path)))
        for base, prefix in ((self.root, ""), (Path(os.path.abspath(str(self.home))), "<home>/")):
            try:
                return prefix + resolved.relative_to(base).as_posix()
            except ValueError:
                continue
        return resolved.as_posix()

    def read(self, path, name, limit=None):
        """The bytes of one input, its hash recorded; unreadable or over the limit is exit 3."""
        limit = TEXT_LIMIT if limit is None else limit
        try:
            size = os.path.getsize(str(path))
        except OSError as exc:
            raise cannot(name, WHOLE, "cannot read the file: %s" % exc, "a readable file")
        if size > limit:
            raise cannot(name, WHOLE, "the file is %d bytes, over the %d-byte limit" % (size, limit),
                         "a smaller file, or the text split into several")
        try:
            data = read_bytes(path)
        except OSError as exc:
            raise cannot(name, WHOLE, "cannot read the file: %s" % exc, "a readable file")
        self.inputs[name] = {"file": name, "sha256": hashlib.sha256(data).hexdigest()}
        return data

    def text(self, path, name):
        """Decoded UTF-8 text, a leading byte-order mark dropped, line endings read as LF (G11)."""
        return decode(self.read(path, name), name)[0]

    def absent(self, name):
        self.inputs.setdefault(name, {"file": name, "state": "absent"})

    def add(self, finding):
        self.order += 1
        finding["_order"] = finding.get("_order", (9, finding["file"], 0, 0, self.order))
        self.findings.append(finding)


def decode(data, name):
    """(LF text, raw offsets): the decoded text with CRLF and CR read as LF, and each character's offset in the
    decoded text as stored, so a span names the file's own characters (X23)."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise cannot(name, WHOLE, "the file is not UTF-8: %s" % exc, "a UTF-8 text file")
    if "\r" not in text:
        return text, None
    out, raw, i = [], [], 0
    while i < len(text):
        if text[i] == "\r":
            out.append("\n")
            raw.append(i)
            i += 2 if text[i + 1:i + 2] == "\n" else 1
            continue
        out.append(text[i])
        raw.append(i)
        i += 1
    return "".join(out), raw


def json_value(text, name):
    try:
        return json.loads(text)
    except ValueError as exc:
        raise cannot(name, WHOLE, "not valid JSON: %s" % exc, "a JSON value")


# The lists: the shipped list, the local list, the settings' firm and account structure (X04, X33, nod 8).

class Row:
    __slots__ = ("kind", "cls", "term", "line", "list", "regex", "parent")

    def __init__(self, kind, cls, term, line, source, regex=None, parent=None):
        self.kind, self.cls, self.term, self.line, self.list = kind, cls, term, line, source
        self.regex, self.parent = regex, parent

    def where(self):
        return "%s line %d" % (self.list, self.line)


def parse_list(text, name, local):
    """Rows of the leak-terms syntax (LT:17 to 29) with X33's rules; anything it cannot apply is exit 3."""
    rows, cls, phonetic = [], None, None
    for number, raw in enumerate(text.split("\n"), 1):
        line = raw.strip()
        field = "line %d" % number
        if not line or line.startswith("#"):
            continue
        if line.startswith("class:"):
            cls = line[6:].strip()
            if not CLASS_NAME.fullmatch(cls):
                raise cannot(name, field, "the class name %r is not letters, digits and hyphens" % cls,
                             "class: <name>, the name in letters, digits and hyphens")
            phonetic = None
            continue
        if cls is None and not local:
            raise cannot(name, field, "a row above the first class line", "every row of the shipped list under a "
                         "class: line")
        row_cls = cls or LOCAL_CLASS
        if line.startswith("re:"):
            pattern = line[3:].strip()
            if not pattern:
                raise cannot(name, field, "a re: row with no pattern", "re: <a Python regular expression>")
            if local and NESTED.search(pattern):
                raise cannot(name, field, "a pattern that can run for a very long time (a quantified group that "
                             "holds a quantifier)", "a pattern without a repeated group that itself repeats")
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except re.error as exc:
                raise cannot(name, field, "the pattern does not compile: %s" % exc, "a Python regular expression")
            rows.append(Row("re", row_cls, pattern, number, name, regex=regex))
            phonetic = None
        elif line.startswith("phonetic:"):
            term = line[9:].strip()
            if not words_of(term):
                raise cannot(name, field, "a phonetic: row with no term", "phonetic: <term>")
            phonetic = Row("phonetic", row_cls, term, number, name)
            rows.append(phonetic)
        elif line.startswith("whitelist:"):
            term = line[10:].strip()
            if not words_of(term):
                raise cannot(name, field, "a whitelist: row with no term", "whitelist: <term>")
            if row_cls != "firm" and phonetic is None:
                raise cannot(name, field, "a whitelist: row with no phonetic: row directly above it",
                             "a whitelist: row under the phonetic: row whose legitimate use it names")
            rows.append(Row("whitelist", row_cls, term, number, name, parent=None if row_cls == "firm" else phonetic))
        else:
            rows.append(Row("literal", row_cls, line, number, name))
            phonetic = None
    return rows


class Pattern:
    """One compiled literal: its rule, class, the row it came from, and whether it is counted rather than blocked."""
    __slots__ = ("rule", "cls", "regex", "origin", "term", "counted")

    def __init__(self, rule, cls, regex, origin, term, counted=False):
        self.rule, self.cls, self.regex, self.origin, self.term, self.counted = rule, cls, regex, origin, term, counted


FUSED_CLASSES = ("firm", "plugin")


class Lists:
    """Everything the term rules read: the literal and re: rows of both lists, the firm's renderings and phonetic
    sources, the seller's own account structure, and the embedded vocabulary groups."""

    def __init__(self, rows, settings):
        self.rows, self.literals, self.regexes, self.phonetic, self.id_row = rows, [], [], [], None
        self.firm_whitelist = [row.term for row in rows if row.kind == "whitelist" and row.cls == "firm"]
        self.category_words = set()
        for row in rows:
            fused = row.cls in FUSED_CLASSES
            if row.kind in ("literal", "phonetic"):
                counted = row.cls.startswith(COUNTED_PREFIX)
                regex = literal_regex(row.term, tokenised=fused, fused=fused)
                if regex is not None:
                    self.literals.append(Pattern("term", row.cls, regex, row.where(), row.term, counted))
                if counted:
                    self.category_words.update(words_of(row.term))
            if row.kind == "re":
                if row.cls == "id-patterns" and row.term == ID_ROW:
                    self.id_row = row
                self.regexes.append(row)
            if row.kind == "phonetic":
                whitelist = self.firm_whitelist if row.cls == "firm" else \
                    [r.term for r in rows if r.kind == "whitelist" and r.parent is row]
                self.phonetic.append(PhoneticSource(row.cls, row.term, row.where(), whitelist))
        firm = settings["firm"]
        for term in [firm["name"]] + list(firm["renderings"]):
            where = "%s firm" % SETTINGS_NAME
            self.literals.append(Pattern("term", "firm", literal_regex(term, True, True), where, term))
            self.phonetic.append(PhoneticSource("firm", term, where, self.firm_whitelist))
        for term, what in settings["seller_names"]:
            self.literals.append(Pattern("seller-account", "seller-account", literal_regex(term, True, True),
                                         "%s %s" % (SETTINGS_NAME, what), term))
        self.seller_ids = settings["seller_ids"]
        for cls, group in (("internal-vocabulary", INTERNAL_VOCABULARY), ("sales-framing", SALES_FRAMING)):
            for term in group:
                self.literals.append(Pattern("term", cls, literal_regex(term), "the %s group" % cls, term))
        for term in INTERNAL_NOTE_PHRASES:
            self.literals.append(Pattern("internal-note", None, literal_regex(term), "the internal-notes group", term))
        self.plugin_words = set()
        for row in rows:
            if row.kind == "literal" and row.cls in ("plugin", "assistant", "method", "markers"):
                self.plugin_words.update(words_of(row.term))


def load_shipped(run):
    path = PLUGIN / "shared" / "leak-terms.txt"
    if not path.is_file():
        raise cannot(SHIPPED_NAME, WHOLE, "the shipped list is missing", "shared/leak-terms.txt of the plugin")
    rows = parse_list(run.text(path, SHIPPED_NAME), SHIPPED_NAME, local=False)
    if not any(row.kind == "re" and row.cls == "id-patterns" and row.term == ID_ROW for row in rows):
        raise cannot(SHIPPED_NAME, "class id-patterns", "the eight-digit monday id row is missing",
                     "the id-patterns row re: %s, which alone skips links (X34)" % ID_ROW)
    return rows


def load_local(run):
    path = run.home / "local" / "leak-terms.txt"
    if not path.exists():
        run.absent(LOCAL_NAME)
        return []
    if not path.is_file():
        raise cannot(LOCAL_NAME, WHOLE, "the local list is not a file", "a text file, or none")
    return parse_list(run.text(path, LOCAL_NAME), LOCAL_NAME, local=True)


def load_settings(run):
    """local/settings.json: schema settings/1 and a firm with a name, required; the seller's names and ids read."""
    path = run.home / "local" / "settings.json"
    if not path.is_file():
        raise cannot(SETTINGS_NAME, WHOLE, "there is no settings file, so the firm rule cannot run",
                     "local/settings.json under the home, as record.py home init writes it, with the firm block")
    data = json_value(run.text(path, SETTINGS_NAME), SETTINGS_NAME)
    if not isinstance(data, dict):
        raise cannot(SETTINGS_NAME, WHOLE, "the file is not a JSON object", "a settings/1 object")
    schema = data.get("schema")
    if schema != "settings/1":
        problem = "schema %s is newer than this plugin's or not this file's" % schema \
            if isinstance(schema, str) and mc.schema_newer(schema, "settings") else "schema %r is not settings/1" % schema
        raise cannot(SETTINGS_NAME, "schema", problem, "settings/1")
    firm = data.get("firm")
    if not isinstance(firm, dict) or not isinstance(firm.get("name"), str) or not words_of(firm.get("name") or ""):
        raise cannot(SETTINGS_NAME, "firm.name", "the firm has no name, so the firm rule cannot run",
                     "firm.name, the user's own firm name, which the first-run walkthrough writes")
    renderings = firm.get("renderings", [])
    if not isinstance(renderings, list) or not all(isinstance(r, str) and words_of(r) for r in renderings):
        raise cannot(SETTINGS_NAME, "firm.renderings", "the renderings are not a list of non-empty strings",
                     "firm.renderings, a list of strings (it may be empty)")
    names, ids = [], []

    def text_field(value, field):
        if value in (None, ""):
            return None
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise cannot(SETTINGS_NAME, field, "not a string", "a string")
        return str(value).strip() or None

    account = data.get("default_build_account")
    if account is not None:
        if not isinstance(account, dict):
            raise cannot(SETTINGS_NAME, "default_build_account", "not an object", "{slug, id}")
        slug, ident = text_field(account.get("slug"), "default_build_account.slug"), \
            text_field(account.get("id"), "default_build_account.id")
        if slug and words_of(slug):
            names.append((slug, "default_build_account.slug"))
        if ident:
            ids.append((ident, "default_build_account.id"))
    shown = data.get("never_show_workspaces", [])
    if shown is None:
        shown = []
    if not isinstance(shown, list):
        raise cannot(SETTINGS_NAME, "never_show_workspaces", "not a list", "a list of {id, name}")
    for index, item in enumerate(shown):
        field = "never_show_workspaces[%d]" % index
        if not isinstance(item, dict):
            raise cannot(SETTINGS_NAME, field, "not an object", "{id, name}")
        name, ident = text_field(item.get("name"), field + ".name"), text_field(item.get("id"), field + ".id")
        if name and words_of(name):
            names.append((name, field + ".name"))
        if ident:
            ids.append((ident, field + ".id"))
    github = text_field(data.get("github_account"), "github_account")
    if github and words_of(github):
        names.append((github, "github_account"))
    seller_ids = []
    for ident, field in ids:
        forms = {ident, ident.lstrip("0") or ident} if ident.isdigit() else {ident}
        for form in sorted(forms):
            seller_ids.append((re.compile(r"(?<!\d)%s(?!\d)" % re.escape(fold_text(form))), form, field))
    return {"firm": {"name": firm["name"], "renderings": renderings}, "seller_names": names, "seller_ids": seller_ids}


def load_lists(run):
    """The shipped list, the local list and the settings, read on every command that runs the firm rule."""
    if run.lists is None:
        rows = load_shipped(run) + load_local(run)
        run.lists = Lists(rows, load_settings(run))
    return run.lists


# Numbers (X25): digits with separators, currency and magnitude, number words, percentages; dates, times, versions,
# a year alone and list ordinals are not numbers. Values are exact fractions; precision is the unit of the last
# written digit.

UNITS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
TEENS = {"ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
         "seventeen": 17, "eighteen": 18, "nineteen": 19}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
BIG = {"thousand": 1000, "grand": 1000, "million": 10 ** 6, "billion": 10 ** 9}
NUMBER_WORDS = frozenset(set(UNITS) | set(TEENS) | set(TENS) | set(BIG) | {"hundred", "and", "a", "point", "half",
                                                                           "quarter", "of"})
NUMBER_START = frozenset(set(UNITS) | set(TEENS) | set(TENS) | {"a", "half"})
WORD_GAP = re.compile(r"[ \t]+|[ \t]*-[ \t]*|[ \t]*-?[ \t]*\n[ \t]*")
_CURRENCY = r"[$£€¥]|(?:" + "|".join(CURRENCY_CODES) + r")\b"
NUMBER = re.compile(r"(?<![\w.,' /-])(?P<pre>(?:" + _CURRENCY + r")[ \t]?)?"
                    r"(?P<int>\d{1,3}(?:[,' ]\d{3})+(?!\d)|\d+)(?P<dec>\.\d+)?"
                    r"(?P<mag>[ \t]?(?:thousand|million|billion|grand|bn|mm|k|m)(?![^\W\d_]))?"
                    r"(?P<pct>[ \t]?(?:%|percent\b|per[ \t]+cent\b))?"
                    r"(?P<post>[ \t]?(?:" + _CURRENCY + r"))?(?![^\W_])")
MAGNITUDE = {"k": 1000, "thousand": 1000, "grand": 1000, "m": 10 ** 6, "mm": 10 ** 6, "million": 10 ** 6,
             "bn": 10 ** 9, "billion": 10 ** 9}
PERCENT_AFTER = re.compile(r"[ \t]?(?:%|percent\b|per[ \t]+cent\b)")
RATE_AFTER = re.compile(RATE_SUFFIX)
_MONTH = (r"(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|"
          r"apr|jun|jul|aug|sept|sep|oct|nov|dec)")
MONTHS = {name: number for number, names in enumerate(
    (("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"), ("may",), ("june", "jun"),
     ("july", "jul"), ("august", "aug"), ("september", "sep", "sept"), ("october", "oct"), ("november", "nov"),
     ("december", "dec")), 1) for name in names}
DATE_YMD = re.compile(r"(?<![\d.])(\d{4})(?:-|/|\.)(\d{1,2})(?:-|/|\.)(\d{1,2})(?![\d])")
DATE_DMY = re.compile(r"(?<![\d.])(\d{1,2})(?:-|/|\.)(\d{1,2})(?:-|/|\.)(\d{4})(?![\d])")
DATE_DAY_MONTH = re.compile(r"(?<![\d.])(\d{1,2})(?:st|nd|rd|th)?[ \t]+(?:of[ \t]+)?(" + _MONTH + r")\b\.?"
                            r"(?:,?[ \t]+(\d{4}))?(?!\d)")
DATE_MONTH_DAY = re.compile(r"\b(" + _MONTH + r")\b\.?[ \t]+(\d{1,2})(?:st|nd|rd|th)?\b(?:,?[ \t]+(\d{4}))?(?!\d)")
DATE_MONTH_YEAR = re.compile(r"\b(" + _MONTH + r")\b\.?[ \t]+(\d{4})(?!\d)")
TIMES = (re.compile(r"(?<![\d:])\d{1,2}:\d{2}(?::\d{2})?(?![\d:])(?:[ \t]?[ap]\.?m\b\.?)?"),
         re.compile(r"(?<![\d.])\d{1,2}[ \t]?[ap]\.?m\b\.?"))
VERSIONS = (re.compile(r"\bv\d+(?:\.\d+)+\b"), re.compile(r"(?<![\d.])\d+\.\d+\.\d+(?:\.\d+)*(?![\d.])"))
YEAR = re.compile(r"(?<![\d$£€¥.,' ])(?<![$£€¥] )(?:19|20)\d{2}(?![\d%])(?![ \t]?(?:k|mm|m|bn|thousand|million|"
                  r"billion|grand|percent)(?![^\W\d_]))")
ORDINAL = re.compile(r"(?m)^[ \t]*(?:#{1,6}[ \t]+|[-*+>][ \t]+)?(\d{1,3})[.)](?=[ \t]|$)")
DIGIT_RUN = re.compile(r"\d+")
CHAIN_JOIN = re.compile(r"[ \t]|[ \t]*\n[ \t]*|[ \t]*\|[ \t]*|[ \t]?[*_~`]+[ \t]?")
CHAIN_THREE = re.compile(r"[.\-/_]")
ID_JOIN = re.compile(r"[ .\-]")
COST_RE = re.compile(r"[$£€¥]|(?<!%s)(?:%s)(?!%s)" % (WORDCHAR, "|".join(
    "[\\s-]+".join(re.escape(w) for w in cue.split()) for cue in sorted(COST_CUES + CURRENCY_CODES, key=len,
                                                                         reverse=True)), WORDCHAR))


def valid_date(year, month, day):
    try:
        date(int(year), int(month), int(day))
    except ValueError:
        return False
    return 1900 <= int(year) <= 2099


def date_spans(text):
    """Spans of well-formed dates and times, and of versions: never figures and never warned (X25)."""
    spans = []
    for match in DATE_YMD.finditer(text):
        if valid_date(match.group(1), match.group(2), match.group(3)):
            spans.append(match.span())
    for match in DATE_DMY.finditer(text):
        a, b, year = match.groups()
        if valid_date(year, b, a) or valid_date(year, a, b):
            spans.append(match.span())
    for pattern, order in ((DATE_DAY_MONTH, "dm"), (DATE_MONTH_DAY, "md")):
        for match in pattern.finditer(text):
            day, month = (match.group(1), match.group(2)) if order == "dm" else (match.group(2), match.group(1))
            if valid_date(match.group(3) or 2000, MONTHS[month], day):
                spans.append(match.span())
    spans += [m.span() for m in DATE_MONTH_YEAR.finditer(text)]
    for pattern in TIMES + VERSIONS:
        spans += [m.span() for m in pattern.finditer(text)]
    return spans


def number_masks(text):
    """Date, time and version spans, then a year written alone and the ordinals of a list."""
    spans = date_spans(text)
    spans += [m.span() for m in YEAR.finditer(text)]
    spans += [m.span(1) for m in ORDINAL.finditer(text)]
    return sorted(spans)


def overlaps(spans, start, end):
    return any(s < end and start < e for s, e in spans)


def precision_of(value):
    """The unit of the last written digit of a value spelled in words: 45,000 has 1,000; 1.2 has 0.1."""
    if value == 0:
        return Fraction(1)
    if value.denominator != 1:
        k = 0
        while (value * 10 ** k).denominator != 1 and k < 12:
            k += 1
        return Fraction(1, 10 ** k)
    unit, number = 1, int(value)
    while number % 10 == 0:
        number //= 10
        unit *= 10
    return Fraction(unit)


def words_number(words):
    """(value, count) of the longest number the words begin with, or (None, 0)."""
    if len(words) >= 3 and words[0] == "half" and words[1] == "a" and words[2] in BIG and words[2] != "grand":
        return Fraction(BIG[words[2]], 2), 3
    if len(words) >= 5 and words[:4] == ["a", "quarter", "of", "a"] and words[4] in BIG and words[4] != "grand":
        return Fraction(BIG[words[4]], 4), 5
    total, group, state, big_last, best, i = Fraction(0), Fraction(0), None, None, (None, 0), 0
    while i < len(words):
        word = words[i]
        if word == "a":
            if state is not None or i + 1 >= len(words) or words[i + 1] not in ("hundred", "thousand", "million",
                                                                                "billion"):
                break
            group, state, i = Fraction(1), "unit", i + 1
            continue
        if word in UNITS or word in TEENS:
            value = UNITS.get(word, TEENS.get(word))
            if not (state == "ten" and word in UNITS and value) and state not in (None, "hundred", "and", "big"):
                break
            group, state = group + value, ("teen" if word in TEENS else "unit")
        elif word in TENS:
            if state not in (None, "hundred", "and", "big"):
                break
            group, state = group + TENS[word], "ten"
        elif word == "hundred":
            if state not in ("unit", "teen", "ten") or group >= 100:
                break
            group, state = group * 100, "hundred"
        elif word in BIG:
            scale = BIG[word]
            if state in (None, "and") or (big_last is not None and scale >= big_last):
                break
            total, group, big_last, state = total + group * scale, Fraction(0), scale, "big"
        elif word == "and":
            if state not in ("hundred", "big"):
                break
            state, i = "and", i + 1
            continue
        elif word == "point":
            if state not in ("unit", "teen", "ten"):
                break
            j, digits = i + 1, ""
            while j < len(words) and words[j] in UNITS:
                digits, j = digits + str(UNITS[words[j]]), j + 1
            if not digits:
                break
            group, state, i = group + Fraction(int(digits), 10 ** len(digits)), "point", j
            best = (total + group, i)
            continue
        else:
            break
        i += 1
        best = (total + group, i)
    return best


class Number:
    """One number read from a text: its value and precision, where it is, and what is written beside it."""
    __slots__ = ("value", "precision", "percent", "currency", "rate", "start", "end", "split", "cue", "digits",
                 "plain")

    def __init__(self, value, precision, start, end, percent=False, currency=False, rate=False, split=False,
                 digits=False, plain=False):
        self.value, self.precision, self.start, self.end = value, precision, start, end
        self.percent, self.currency, self.rate, self.split = percent, currency, rate, split
        self.cue, self.digits, self.plain = False, digits, plain

    def matches(self, value, precision):
        return abs(self.value - value) < max(self.precision, precision)


def parse_numbers(folded, original, masks=None):
    """Every number of a folded text: digits (with both readings of a lower-case m) and number words; each knows
    whether its sentence holds a cost cue (X25)."""
    text = folded.text
    masks = number_masks(text) if masks is None else masks
    found = []
    for match in NUMBER.finditer(text):
        if overlaps(masks, match.start("int"), match.end("int")):
            continue
        integer = re.sub(r"[,' ]", "", match.group("int"))
        decimals = (match.group("dec") or "")[1:]
        value = Fraction(int(integer + decimals), 10 ** len(decimals))
        precision = Fraction(1, 10 ** len(decimals))
        currency = bool(match.group("pre") or match.group("post"))
        percent = bool(match.group("pct"))
        rate = bool(RATE_AFTER.match(text, match.end()))
        magnitude = (match.group("mag") or "").strip()
        readings = [1]
        if magnitude:
            scale = MAGNITUDE[magnitude]
            start, _ = folded.span(match.start("mag"), match.end("mag"))
            lower = magnitude in ("m", "mm") and original[start:start + 1].islower() and not currency
            readings = [scale, 1] if lower else [scale]
        for scale in readings:
            found.append(Number(value * scale, precision * scale, match.start(), match.end(), percent, currency,
                                rate, digits=True, plain=not magnitude and not decimals and not currency))
    words = [(m.group(), m.start(), m.end()) for m in re.finditer(r"[a-z]+", text)]
    i = 0
    while i < len(words):
        if words[i][0] not in NUMBER_START:
            i += 1
            continue
        run, j = [words[i]], i
        while j + 1 < len(words) and words[j + 1][0] in NUMBER_WORDS and \
                WORD_GAP.fullmatch(text[words[j][2]:words[j + 1][1]]):
            run.append(words[j + 1])
            j += 1
        value, count = words_number([w for w, _, _ in run])
        if value is None or count == 0:
            i += 1
            continue
        used = run[:count]
        start, end = used[0][1], used[-1][2]
        split = any("\n" in text[used[k][2]:used[k + 1][1]] for k in range(len(used) - 1))
        after = PERCENT_AFTER.match(text, end)
        number = Number(value, precision_of(value), start, after.end() if after else end, percent=bool(after),
                        rate=bool(RATE_AFTER.match(text, end)), split=split)
        found.append(number)
        i += count
    sentences = sentence_spans(text)
    starts = [s for s, _ in sentences]
    cues = [bool(COST_RE.search(text, s, e)) for s, e in sentences]
    for number in found:
        index = max(0, bisect.bisect_right(starts, number.start) - 1)
        number.cue = cues[index] if cues else False
    return found


def digit_chains(text, masks):
    """Digit groups joined by single spaces, a line break, a table pipe or emphasis marks, or by a dot, hyphen,
    slash or underscore before a group of three: a figure in split rendering, read as one number (X25)."""
    chains, current = [], []

    def close():
        if len(current) >= 2:
            chains.append(list(current))
        del current[:]

    for match in DIGIT_RUN.finditer(text):
        s, e = match.span()
        if (s and text[s - 1].isalpha()) or (e < len(text) and text[e].isalpha()) or overlaps(masks, s, e):
            close()
            continue
        if current:
            separator = text[current[-1][1]:s]
            if CHAIN_JOIN.fullmatch(separator) or (CHAIN_THREE.fullmatch(separator) and e - s == 3):
                current.append((s, e))
                continue
            close()
        current.append((s, e))
    close()
    return chains


def chain_is_date(text, groups):
    """Y02: three groups of 1-2, 1-2 and 4 digits (or 4, 2 and 2) that form a real date are a date."""
    if len(groups) != 3:
        return False
    parts = [text[s:e] for s, e in groups]
    sizes = [len(p) for p in parts]
    if sizes[2] == 4 and sizes[0] <= 2 and sizes[1] <= 2:
        return valid_date(parts[2], parts[1], parts[0]) or valid_date(parts[2], parts[0], parts[1])
    if sizes[0] == 4 and sizes[1] <= 2 and sizes[2] <= 2:
        return valid_date(parts[0], parts[1], parts[2])
    return False


def id_chains(text):
    """X34: digit groups of two to four joined by single spaces, hyphens or dots, eight digits or more in all."""
    chains, current = [], []

    def close():
        if len(current) >= 2 and sum(e - s for s, e in current) >= 8:
            chains.append(list(current))
        del current[:]

    for match in DIGIT_RUN.finditer(text):
        s, e = match.span()
        good = 2 <= e - s <= 4 and not (s and (text[s - 1].isalnum() or text[s - 1] in "/:")) and \
            not (e < len(text) and (text[e].isalnum() or text[e] == ":"))
        if not good:
            close()
            continue
        if current and not ID_JOIN.fullmatch(text[current[-1][1]:s]):
            close()
        current.append((s, e))
    close()
    return chains


def whole_number(term):
    """The one number a term reads as, when the whole term is that number (an exclusion's figure row), else None."""
    folded = fold(term.strip())
    found = [n for n in parse_numbers(folded, term.strip(), masks=[]) if n.start == 0 and n.end == len(folded.text)]
    return found[0] if found else None


# The record's own sets (X11, Y01): F the figures, R the internal runs, Q the client quotes and E the client's
# document text, the exemption source of the copied-run rule. Read fresh on every run; nothing is cached.

class Segment:
    __slots__ = ("file", "part", "text", "flags")

    def __init__(self, file, part, text, flags):
        self.file, self.part, self.text, self.flags = file, part, text, flags


def blank_marks(text):
    """Y03: a line that is exactly one of the four marks is never checked text; its characters become spaces."""
    if "<!--" not in text:
        return text
    lines = text.split("\n")
    return "\n".join(" " * len(line) if line.strip() in BLOCK_MARKS else line for line in lines)


def block_lines(lines, start_mark, end_mark):
    """(set of line indexes inside well-formed blocks, problem or None): X09's marks, several blocks allowed; a
    mark out of order exempts nothing and gives the 1-based line and the problem."""
    inside_lines, open_at = set(), None
    for index, line in enumerate(lines):
        mark = line.strip()
        if mark == start_mark:
            if open_at is not None:
                return set(), (index + 1, "a second opening mark inside an open block")
            open_at = index
        elif mark == end_mark:
            if open_at is None:
                return set(), (index + 1, "a closing mark with no opening mark")
            inside_lines.update(range(open_at + 1, index))
            open_at = None
    if open_at is not None:
        return set(), (open_at + 1, "an opening mark with no closing mark")
    return inside_lines, None


def section_lines(lines, title):
    """Indexes of the lines under a level-2 heading `title` (letter case ignored), up to the next level 1 or 2."""
    found, active = set(), False
    for index, line in enumerate(lines):
        heading = HEADING.match(line)
        if heading and len(heading.group(1)) <= 2:
            active = len(heading.group(1)) == 2 and line.strip().lower() == title.lower()
            continue
        if active:
            found.add(index)
    return found


def blueprint_client_lines(lines):
    """The blueprint's client-facing lines (X09): sections 1 to 15, the prompt blocks, the glossary blocks."""
    found, active = set(), False
    for index, line in enumerate(lines):
        heading = HEADING.match(line)
        if heading and len(heading.group(1)) <= 2:
            number = re.match(r"(\d{1,2})(?:[.\s]|$)", heading.group(2))
            active = len(heading.group(1)) == 2 and bool(number) and 1 <= int(number.group(1)) <= 15
            continue
        if active:
            found.add(index)
    for index, line in enumerate(lines):
        if re.match(r"^###\s+Prompt\s+\S", line):
            j = index + 1
            while j < len(lines) and not lines[j].strip().startswith("```"):
                if HEADING.match(lines[j]):
                    break
                j += 1
            if j < len(lines) and lines[j].strip().startswith("```"):
                k = j + 1
                while k < len(lines) and not lines[k].strip().startswith("```"):
                    found.add(k)
                    k += 1
    glossary, _ = block_lines(lines, BLOCK_MARKS[2], BLOCK_MARKS[3])
    return found | glossary


def is_snapshot(text):
    """A document-summary/1 snapshot: flat front matter whose schema line names it."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return False
    for line in lines[1:]:
        if line.strip() == "---":
            return False
        if SNAPSHOT.match(line.strip()):
            return True
    return False


def quote_texts(line):
    """X24: the client quote a marked line holds: the text between double quotation marks, else the line with the
    marker, the location forms and the speaker label removed."""
    quoted = [m.group(1) for m in QUOTE_SPANS.finditer(line)]
    if quoted:
        return quoted
    rest = line
    for marker in MARKERS[:5]:
        rest = re.sub(re.escape(marker), " ", rest, flags=re.IGNORECASE)
    rest = LOCATION.sub(" ", rest)
    if ":" in rest:
        rest = rest.split(":", 1)[1]
    return [rest]


QUOTE_MARK = re.compile("|".join(re.escape(m) for m in MARKERS[:5]), re.IGNORECASE)
DOC_MARK = re.compile(re.escape(MARKERS[4]), re.IGNORECASE)


def kind_of(rel):
    """What a record file feeds, by its record-relative path (X11, Y01)."""
    parts = rel.split("/")
    name = parts[-1]
    if parts[0] == "inputs":
        return "input"
    if parts[0] == "calls":
        return "call" if name.lower().endswith(".md") else "transcript"
    if parts[-2:] == ["live", "live-map.md"]:
        return "skip"
    if len(parts) >= 3 and parts[0] == "strands":
        tail = parts[2:]
        if tail == ["solution", "exclusions.md"] or tail == ["solution", "allowlist.md"]:
            return "skip"
        if tail == ["solution", "blueprint.md"] or (len(tail) == 3 and tail[0] == "versions" and
                                                   re.fullmatch(r"blueprint-r\d+\.md", tail[2])):
            return "blueprint"
    if rel in ("CLIENT.md", "meetings.md", "log.md"):
        return "plain"
    return "internal"


def skipped_dir(parts):
    """Folders that feed no set: .work/, every strand's drafts/ and deliverables/, and .git/."""
    if parts[-1] in (".work", ".git", "__pycache__"):
        return True
    return len(parts) == 3 and parts[0] == "strands" and parts[2] in ("drafts", "deliverables")


def record_files(run):
    """Every .md, .txt and .docx of the record that may feed a set, in sorted POSIX path order."""
    found = []

    def failed(exc):
        raise cannot(run.name(exc.filename or run.root), WHOLE, "cannot list the folder: %s" % exc,
                     "a readable record folder")

    for folder, dirs, files in os.walk(str(run.root), onerror=failed):
        rel = Path(folder).relative_to(run.root).as_posix()
        parts = () if rel == "." else tuple(rel.split("/"))
        dirs[:] = sorted(d for d in dirs if not skipped_dir(parts + (d,)))
        for name in sorted(files):
            if name.lower() in SYSTEM_FILES or os.path.splitext(name)[1].lower() not in TEXT_EXT:
                continue
            found.append("/".join(parts + (name,)))
    return sorted(found)


def lines_to_segments(file, lines, tags):
    """Contiguous lines with the same tag become one segment; a None tag is left out."""
    segments, current, tag = [], [], None
    for line, this in zip(lines, tags):
        if this != tag and current:
            if tag is not None:
                segments.append(Segment(file, tag[0], "\n".join(current), tag[1]))
            current = []
        tag = this
        current.append(line)
    if current and tag is not None:
        segments.append(Segment(file, tag[0], "\n".join(current), tag[1]))
    return segments


def file_segments(run, rel, text):
    """The segments one record file gives, each tagged with the sets it feeds and with body or block."""
    kind = kind_of(rel)
    if kind == "skip":
        return []
    lines = text.split("\n")
    marks = [line.strip() in BLOCK_MARKS for line in lines]
    body_all, body_noq = ("body", frozenset("FRQ")), ("body", frozenset("FR"))
    if kind in ("plain", "transcript"):
        return lines_to_segments(rel, lines, [None if m else body_noq for m in marks])
    if kind == "internal":
        return lines_to_segments(rel, lines, [None if m else body_all for m in marks])
    if kind == "input" and not (rel.lower().endswith(".md") and is_snapshot(text)):
        return lines_to_segments(rel, lines, [None if m else ("body", frozenset("FE")) for m in marks])
    if kind == "blueprint":
        client = blueprint_client_lines(lines)
        return lines_to_segments(rel, lines, [None if m or i in client else body_all for i, m in enumerate(marks)])
    blocks, problem = block_lines(lines, BLOCK_MARKS[0], BLOCK_MARKS[1])
    if problem:
        run.add(record_warning(rel, problem[0], "client-safe marks not well formed (%s); nothing in this file is "
                               "exempt" % problem[1], "an opening and a closing mark, each alone on its line"))
    conflicts = section_lines(lines, HEADINGS[0])
    tags = []
    for index, mark in enumerate(marks):
        if mark:
            tags.append(None)
        elif index in conflicts:
            tags.append(("body", frozenset("FRQC")))
        elif index in blocks:
            tags.append(("block", frozenset("FQ")))
        else:
            tags.append(body_all)
    segments = lines_to_segments(rel, lines, tags)
    if kind == "input":
        for line in lines:
            if DOC_MARK.search(line):
                for quote in quote_texts(line):
                    segments.append(Segment(rel, "body", quote, frozenset("E")))
    return segments


def record_warning(file, line, problem, expected, rule="copied-run"):
    return {"file": file, "field": "line %d" % line, "problem": problem, "expected": expected, "rule": rule,
            "class": None, "severity": "warn", "line": line, "column": 1, "match": None, "source": None,
            "_order": (9, file, line, 0, 0)}


def docx_text(run, path, name):
    """(text of every part joined, parts read, the parts as (part, paragraphs, labels)) of a .docx (X35)."""
    data = run.read(path, name, limit=DOCX_TOTAL_LIMIT)
    parts = docx_parts(data, name)
    run.inputs[name]["parts_read"] = [part for part, _, _ in parts]
    return parts


class Sets:
    """F, R, Q and E with the file and part each entry came from, so a checked file never feeds its own check."""

    def __init__(self):
        self.cost, self.cost_percent, self.record, self.record_percent = [], [], [], []
        self.runs, self.docs, self.quotes = {}, {}, {}
        self.near_runs = self.near_docs = None
        self.run_tokens, self.doc_tokens = [], []

    def add_numbers(self, segment):
        folded = fold(segment.text)
        for number in parse_numbers(folded, segment.text):
            if number.split or number.value < 10 and not number.percent:
                continue
            if number.percent and number.value < 10:
                continue
            entry = (number.value, number.precision, segment.file, segment.part)
            if number.cue:
                (self.cost_percent if number.percent else self.cost).append(entry)
            else:
                (self.record_percent if number.percent else self.record).append(entry)

    def add_grams(self, index, words, size, entry):
        for i in range(len(words) - size + 1):
            index.setdefault(tuple(words[i:i + size]), []).append(entry)

    def near(self, which):
        """The eight-word windows of R (or E) with each position in turn left open, for the near-copy check."""
        if which == "runs" and self.near_runs is None:
            self.near_runs = near_index(self.run_tokens)
        if which == "docs" and self.near_docs is None:
            self.near_docs = near_index(self.doc_tokens)
        return self.near_runs if which == "runs" else self.near_docs


def near_index(sources):
    index = {}
    for words, entry in sources:
        for i in range(len(words) - NEAR_WORDS + 1):
            window = words[i:i + NEAR_WORDS]
            for position in range(NEAR_WORDS):
                key = (position,) + tuple(window[:position]) + tuple(window[position + 1:])
                index.setdefault(key, []).append(entry)
    return index


def build_sets(run):
    """Read every record file the sets need (X11), listing each with its hash, and build F, R, Q and E."""
    sets = Sets()
    for rel in record_files(run):
        path = run.root.joinpath(*rel.split("/"))
        if rel.lower().endswith(".docx"):
            text = "\n".join("\n".join(paragraphs) for _, paragraphs, _ in docx_text(run, path, rel))
        else:
            text = run.text(path, rel)
        for segment in file_segments(run, rel, text):
            flags = segment.flags
            if "F" in flags:
                sets.add_numbers(segment)
            words = words_of(segment.text)
            if "R" in flags:
                entry = (segment.file, segment.part, "C" in flags)
                sets.add_grams(sets.runs, words, RUN_WORDS, entry)
                sets.run_tokens.append((words, entry))
            if "E" in flags:
                entry = (segment.file, segment.part, False)
                sets.add_grams(sets.docs, words, RUN_WORDS, entry)
                sets.doc_tokens.append((words, entry))
            if "Q" in flags:
                for line in segment.text.split("\n"):
                    if QUOTE_MARK.search(line):
                        for quote in quote_texts(line):
                            sets.add_grams(sets.quotes, words_of(quote), QUOTE_WORDS, (segment.file, segment.part))
    return sets


# The strand's exclusions (every strand) and allowlist (its own strand only), X09, X10, Y05.

ROW_LINE = re.compile(r"^-\s+(.*)$")
KEY_GROUP = re.compile(r"^(.*?)\s*\[([^\[\]]*)\]\s*$")
PAIR = re.compile(r"^\s*([a-z_]+)\s*:\s*(.*?)\s*$")


def row_parts(text):
    """Y05: (term, keys). The keys are the last bracketed group when it ends the line and reads as pinned
    `key: value` pairs separated by semicolons; otherwise the whole text is the term."""
    match = KEY_GROUP.match(text)
    if match:
        pairs = [PAIR.match(piece) for piece in match.group(2).split(";")]
        if pairs and all(p and p.group(1) in ROW_KEYS for p in pairs):
            return match.group(1).strip(), {p.group(1): p.group(2) for p in pairs}
    return text.strip(), {}


def section_rows(text, title, name):
    """(line number, term, keys) of every row under the level-2 heading `title`; an empty term is exit 3."""
    lines = text.split("\n")
    rows = []
    for index in sorted(section_lines(lines, title)):
        match = ROW_LINE.match(lines[index].strip()) if lines[index].strip().startswith("- ") else None
        if not match:
            continue
        term, keys = row_parts(match.group(1))
        if not words_of(term) and not term.strip():
            raise cannot(name, "line %d" % (index + 1), "a row with an empty term",
                         "- <term> [key: value; ...], the term first")
        rows.append((index + 1, term, keys))
    return rows


def strand_folders(run):
    base = run.root / "strands"
    try:
        return [p for p in sorted(base.iterdir()) if p.is_dir() and re.match(r"\d{3}-", p.name)] if base.is_dir() else []
    except OSError as exc:
        raise cannot("strands/", WHOLE, "cannot list the strands: %s" % exc, "a readable strands folder")


def strand_folder(run, short):
    if not re.fullmatch(r"\d{3}", short or ""):
        raise cannot("strands/", "--strand", "%r is not a strand's three-digit short id" % short, "a short id, such "
                     "as 001")
    found = [p for p in strand_folders(run) if p.name.startswith(short + "-")]
    if not found:
        raise cannot("strands/", "--strand", "no strand %s in this record" % short, "a strand's short id")
    return found[0]


class Exclusions:
    """Every strand's exclusion rows: literal names and terms (with the gaps and the fused form), and figures."""

    def __init__(self):
        self.patterns, self.figures = [], []


def load_exclusions(run):
    found = Exclusions()
    for folder in strand_folders(run):
        path = folder / "solution" / "exclusions.md"
        name = run.name(path)
        if not path.exists():
            run.absent(name)
            continue
        for line, term, keys in section_rows(run.text(path, name), HEADINGS[1], name):
            kind = keys.get("kind")
            if kind is not None and kind not in EXCLUSION_KINDS:
                raise cannot(name, "line %d" % line, "the row kind %r is not name, term or figure" % kind,
                             "kind: name, kind: term or kind: figure")
            number = whole_number(term)
            if kind == "figure" and number is None:
                raise cannot(name, "line %d" % line, "a figure row whose term is not a number", "a figure, such as "
                             "45,000 or 45k")
            kind = kind or ("figure" if number is not None else "term")
            where = "%s line %d" % (name, line)
            if kind == "figure":
                found.figures.append((number.value, number.precision, where, term))
            else:
                regex = literal_regex(term, tokenised=True, fused=True)
                if regex is None:
                    raise cannot(name, "line %d" % line, "a row whose term has no letters or digits",
                                 "a name or a term")
                found.patterns.append(Pattern("exclusion", kind, regex, where, term))
    return found


class AllowRow:
    __slots__ = ("term", "normal", "ok", "file", "line")

    def __init__(self, term, ok, file, line):
        self.term, self.normal, self.ok, self.file, self.line = term, normal_form(term), ok, file, line


def load_allowlist(run, short):
    """The allowlist of one strand (X10); a row without a non-empty ok clears nothing and warns on every run."""
    if short is None:
        return []
    if short in run.allowlists:
        return run.allowlists[short]
    path = strand_folder(run, short) / "solution" / "allowlist.md"
    name = run.name(path)
    rows = []
    if not path.exists():
        run.absent(name)
    else:
        for line, term, keys in section_rows(run.text(path, name), HEADINGS[2], name):
            ok = (keys.get("ok") or "").strip()
            row = AllowRow(term, ok, name, line)
            if not ok:
                run.add(record_warning(name, line, "an allowlist row without the user's ok clears nothing",
                                       "the row with ok: and the user's words, or the row removed", "allowlist"))
            rows.append(row)
    run.allowlists[short] = rows
    return rows


# .docx (X35): read in memory, the body and every part that carries text, with the guards of X35 and X42.

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
WORD_PART = re.compile(r"word/(?:document|header\d*|footer\d*|footnotes|endnotes|comments)\.xml")
PROPERTY_PARTS = ("docProps/core.xml", "docProps/app.xml", "docProps/custom.xml")
PREFIXES = {"http://purl.org/dc/elements/1.1/": "dc:", "http://purl.org/dc/terms/": "dcterms:",
            "http://schemas.openxmlformats.org/package/2006/metadata/core-properties": "cp:",
            "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes": "vt:"}
DTD = re.compile(rb"<!\s*(?:DOCTYPE|ENTITY)", re.IGNORECASE)


def element_name(tag):
    if tag.startswith("{"):
        space, _, local = tag[1:].partition("}")
        return PREFIXES.get(space, "") + local
    return tag


def word_paragraphs(root):
    """Each w:p as one line: w:t, w:delText and w:instrText joined with nothing, w:tab a space, w:br a break."""
    paragraphs = []

    def visit(node):
        if node.tag == W_NS + "p":
            pieces = []

            def inner(parent):
                for child in parent:
                    if child.tag == W_NS + "p":
                        visit(child)
                        continue
                    if child.tag in (W_NS + "t", W_NS + "delText", W_NS + "instrText"):
                        pieces.append(child.text or "")
                    elif child.tag == W_NS + "tab":
                        pieces.append(" ")
                    elif child.tag in (W_NS + "br", W_NS + "cr"):
                        pieces.append(" ")
                    inner(child)

            inner(node)
            paragraphs.append("".join(pieces))
            return
        for child in node:
            visit(child)

    visit(root)
    return paragraphs


def property_lines(root):
    """Each element of a property part with text as one line, named by its element (dc:creator, Company)."""
    lines, labels = [], []
    for node in root.iter():
        for value, label in ((node.get("name"), element_name(node.tag) + " name"),
                             (node.text, element_name(node.tag))):
            if value and value.strip():
                lines.append(" ".join(value.split()))
                labels.append(label)
    return lines, labels


def docx_parts(data, name):
    """[(part, lines, labels or None)] of a .docx held in memory; any guard or parse failure is exit 3."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        infos = {info.filename: info for info in archive.infolist()}
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, ValueError) as exc:
        raise cannot(name, WHOLE, "not a .docx (zip) archive: %s" % exc, "a Word document")
    if "word/document.xml" not in infos:
        raise cannot(name, "word/document.xml", "the archive has no word/document.xml", "a Word document")
    wanted = ["word/document.xml"] + sorted(n for n in infos if WORD_PART.fullmatch(n) and n != "word/document.xml") \
        + [n for n in PROPERTY_PARTS if n in infos]
    total, parts = 0, []
    for part in wanted:
        info = infos[part]
        total += info.file_size
        if info.file_size > DOCX_MEMBER_LIMIT or total > DOCX_TOTAL_LIMIT:
            raise cannot(name, part, "the part is larger than the lint reads (%d bytes)" % info.file_size,
                         "a part under %d bytes and an archive under %d in all" % (DOCX_MEMBER_LIMIT, DOCX_TOTAL_LIMIT))
        if info.file_size > DOCX_RATIO_FLOOR and info.compress_size and \
                info.file_size > DOCX_RATIO * info.compress_size:
            raise cannot(name, part, "the part expands more than %d to 1" % DOCX_RATIO, "an ordinary Word document")
        try:
            raw = archive.read(part)
        except (zipfile.BadZipFile, OSError, RuntimeError, ValueError, NotImplementedError) as exc:
            raise cannot(name, part, "cannot read the part: %s" % exc, "a readable Word document")
        if DTD.search(raw):
            raise cannot(name, part, "the part declares a DOCTYPE or an ENTITY", "a Word part without a DTD")
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            raise cannot(name, part, "the part is not well-formed XML: %s" % exc, "a readable Word document")
        if part in PROPERTY_PARTS:
            lines, labels = property_lines(root)
            parts.append((part, lines, labels))
        else:
            parts.append((part, word_paragraphs(root), None))
    return parts


# The checker: one unit of text, every rule its mode runs (X05, X37, X38), then the allowlist (X10, X39).

class Unit:
    """One text the rules check: a text file, a .docx part, or one payload string or number (X22)."""

    def __init__(self, file, text, seq, field=None, part=None, strand=None, mode="full", kind="text",
                 structural=False, raw=None, labels=None):
        self.file, self.text, self.seq, self.field, self.part = file, text, seq, field, part
        self.strand, self.mode, self.kind, self.structural = strand, mode, kind, structural
        self.raw, self.labels = raw, labels
        self.own = (file, ("block",) if mode == "client-safe-block" else ("body", "block"))
        self.line_starts = [0] + [i + 1 for i, c in enumerate(text) if c == "\n"]

    def where(self, offset):
        if self.kind != "text":
            return self.field, None, None
        index = max(0, bisect.bisect_right(self.line_starts, offset) - 1)
        line, column = index + 1, offset - self.line_starts[index] + 1
        if self.part:
            label = self.labels[index] if self.labels and index < len(self.labels) else "paragraph %d" % line
            return "%s %s" % (self.part, label), line, column
        return "line %d" % line, line, column

    def raw_span(self, start, end):
        if self.raw is None:
            return start, end
        last = self.raw[end - 1] + 1 if end > start else self.raw[start] if start < len(self.raw) else len(self.raw)
        return (self.raw[start] if start < len(self.raw) else last), last


PROBLEMS = {
    "term": ("a term of class %s (%s)", "the text without it: client-facing text never carries this term"),
    "phonetic": ("sounds like a term of class %s (%s)", "the text without it, or a whitelist row in the local list "
                                                       "when the word is an ordinary one"),
    "seller-account": ("names the user's own account structure (%s)", "the text without the user's own workspaces, "
                                                                      "accounts and ids"),
    "exclusion": ("a %s the client's exclusions keep out (%s)", "the text without it"),
    "internal-note": ("an internal note mark (%s)", "client-facing words only; internal notes stay in the record"),
    "credential": ("a credential shape (%s)", "no secret in anything written to monday"),
}


class Check:
    """The rules over one unit. Every hit is (rule, class, severity, start, end, problem, expected, extra)."""

    def __init__(self, run, unit):
        self.run, self.unit, self.lists, self.sets = run, unit, run.lists, run.sets
        self.text = blank_marks(unit.text)
        self.vf = fold(self.text)
        decoded = percent_decode(plain(self.text)) if "%" in self.text else None
        self.vfd = fold_variant(decoded) if decoded is not None and decoded.text != self.text else None
        self.tokens = tokenise(self.text, self.vf)
        self.hits, self.counted = [], []
        self.links = link_spans(self.vf.text)

    def hit(self, rule, cls, severity, start, end, problem, expected, source=None, **extra):
        self.hits.append((rule, cls, severity, start, end, problem, expected, source, extra))

    def usable(self, entry):
        file, part = entry[0], entry[1]
        return not (file == self.unit.own[0] and part in self.unit.own[1])

    # Literal rows of every list, the firm, the seller's names, the vocabulary groups, notes, exclusions.

    def literals(self):
        patterns = list(self.lists.literals) + list(self.run.exclusions.patterns)
        summary = self.unit.mode == "summary"
        for variant_index, variant in enumerate([self.vf] + ([self.vfd] if self.vfd else [])):
            for pattern in patterns:
                if summary and not pattern.counted:
                    continue
                if pattern.counted and variant_index:
                    continue
                for match in pattern.regex.finditer(variant.text):
                    start, end = variant.span(match.start(), match.end())
                    if pattern.counted:
                        self.counted.append((pattern.cls, match.start(), match.end(), start, end))
                        continue
                    if pattern.rule == "term":
                        problem = PROBLEMS["term"][0] % (pattern.cls, pattern.origin)
                        expected = PROBLEMS["term"][1]
                    elif pattern.rule == "seller-account":
                        problem, expected = PROBLEMS["seller-account"][0] % pattern.origin, PROBLEMS["seller-account"][1]
                    elif pattern.rule == "exclusion":
                        problem, expected = PROBLEMS["exclusion"][0] % (pattern.cls, pattern.origin), \
                            PROBLEMS["exclusion"][1]
                    else:
                        problem, expected = PROBLEMS["internal-note"][0] % pattern.term, PROBLEMS["internal-note"][1]
                    cls = "seller-account" if pattern.rule == "seller-account" else pattern.cls
                    self.hit(pattern.rule, cls, "block", start, end, problem, expected,
                             pattern.origin.split(" line ")[0] if pattern.rule == "exclusion" else None)

    # re: rows line by line, on the line as written, with backslashes as slashes, percent-decoded and folded (X03).

    def lines(self):
        position = 0
        for line in self.text.split("\n"):
            yield position, line
            position += len(line) + 1

    def variants_of(self, start, line):
        base = plain(line, start)
        found = [base]
        if "\\" in line:
            found.append(slashed(base))
        if "%" in line:
            decoded = percent_decode(base)
            found += [decoded, slashed(decoded)]
        folded = fold_variant(base)
        if folded.text != line.lower():
            found.append(folded)
            if "\\" in line:
                found.append(slashed(folded))
        return found

    def regex_rows(self):
        id_row = self.lists.id_row
        for start, line in self.lines():
            if not line.strip():
                continue
            variants = self.variants_of(start, line)
            masked = None
            for row in self.lists.regexes:
                is_id = row is id_row
                if is_id and self.unit.structural:
                    continue
                if is_id and masked is None:
                    masked = [Variant(mask(v.text, link_spans(v.text)), v.offsets) for v in variants]
                for variant in (masked if is_id else variants):
                    for begin, finish in windows(len(variant.text)):
                        if is_id:
                            for match in ID_WIDE.finditer(variant.text, begin, finish):
                                s, e = variant.span(match.start(), match.end())
                                self.hit("term", row.cls, "block", s, e, PROBLEMS["term"][0] % (row.cls, row.where()),
                                         PROBLEMS["term"][1])
                        for match in row.regex.finditer(variant.text, begin, finish):
                            if match.end() == match.start():
                                continue
                            s, e = variant.span(match.start(), match.end())
                            self.hit("term", row.cls, "block", s, e, PROBLEMS["term"][0] % (row.cls, row.where()),
                                     PROBLEMS["term"][1])

    def notes_and_credentials(self):
        lines = list(self.lines())
        for index, (start, line) in enumerate(lines):
            if not line.strip():
                continue
            match = re.match(FRONT_MATTER_LINE, line)
            if match:
                self.hit("internal-note", None, "block", start, start + match.end(), PROBLEMS["internal-note"][0] %
                         "a front-matter line", PROBLEMS["internal-note"][1])
            if line.strip() == "---" and index + 1 < len(lines) and \
                    lines[index + 1][1].strip().lower().startswith("schema:"):
                s = start + line.index("-")
                self.hit("internal-note", None, "block", s, s + 3, PROBLEMS["internal-note"][0] %
                         "a front-matter block", PROBLEMS["internal-note"][1])
            folded = fold_variant(plain(line, start))
            for match in re.finditer(SPEAKER_LABEL, folded.text):
                s, e = folded.span(match.start(), match.end())
                self.hit("internal-note", None, "block", s, e, PROBLEMS["internal-note"][0] % "a speaker label",
                         PROBLEMS["internal-note"][1])
            variants = [plain(line, start)]
            if "%" in line:
                variants.append(percent_decode(variants[0]))
            for variant in variants:
                for shape, pattern, flags in CREDENTIAL_SHAPES:
                    for match in re.finditer(pattern, variant.text, flags):
                        s, e = variant.span(match.start(), match.end())
                        self.hit("credential", None, "block", s, e, PROBLEMS["credential"][0] % shape,
                                 PROBLEMS["credential"][1])
                outside = mask(variant.text, link_spans(variant.text))
                for match in re.finditer(LONG_SECRET, outside):
                    value = match.group()
                    if any(c.isdigit() for c in value) and any(c.islower() for c in value) and \
                            any(c.isupper() for c in value):
                        s, e = variant.span(match.start(), match.end())
                        self.hit("credential", None, "block", s, e, PROBLEMS["credential"][0] % "a long mixed string",
                                 PROBLEMS["credential"][1])

    def seller_ids(self):
        for variant in [self.vf] + ([self.vfd] if self.vfd else []):
            for regex, form, field in self.lists.seller_ids:
                for match in regex.finditer(variant.text):
                    s, e = variant.span(match.start(), match.end())
                    self.hit("seller-account", "seller-account", "block", s, e,
                             PROBLEMS["seller-account"][0] % ("%s %s" % (SETTINGS_NAME, field)),
                             PROBLEMS["seller-account"][1])

    # The phonetic rule (X32, Y09) with its whitelist.

    def phonetic(self):
        sources = self.lists.phonetic
        if not sources or not self.tokens:
            return
        words = [t.word for t in self.tokens]
        keys = [phonetic_key(w) for w in words]
        spelled = [letters(w) for w in words]
        literal = [(h[3], h[4], h[1]) for h in self.hits if h[0] == "term"]
        found = []
        for source in sources:
            cleared = self.whitelist_spans(source.whitelist)
            sizes = sorted({1, len(source.words), len(source.words) + 1})
            for size in sizes:
                for i in range(len(self.tokens) - size + 1):
                    group = self.tokens[i:i + size]
                    if group[0].paragraph != group[-1].paragraph:
                        continue
                    joined = "".join(spelled[i:i + size])
                    if len(joined) < 4:
                        continue
                    if size == 1:
                        candidate = {keys[i]}
                    else:
                        candidate = {" ".join(keys[i:i + size]), "".join(keys[i:i + size])}
                    near = source.limit and edit_distance(joined, source.letters, source.limit) <= source.limit
                    if not (candidate & source.keys or near):
                        continue
                    span = (i, i + size)
                    shown = normal_form(self.text[group[0].start:group[-1].end])
                    if any(shown == normal_form(term) for term in source.whitelist) or \
                            any(a <= span[0] and span[1] <= b for a, b in cleared):
                        continue
                    start, end = group[0].start, group[-1].end
                    if any(s < end and start < e and c == source.cls for s, e, c in literal):
                        continue
                    found.append((start, end, source))
        found.sort(key=lambda f: (f[0], -f[1]))
        merged = []
        for start, end, source in found:
            if merged and merged[-1][2].cls == source.cls and start < merged[-1][1]:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]), merged[-1][2])
                continue
            merged.append((start, end, source))
        for start, end, source in merged:
            self.hit("phonetic", source.cls, "block", start, end, PROBLEMS["phonetic"][0] % (source.cls, source.origin),
                     PROBLEMS["phonetic"][1])

    def whitelist_spans(self, terms):
        """Token ranges of every occurrence of a whitelist row in the text."""
        spans, words = [], [t.word for t in self.tokens]
        for term in terms:
            target = words_of(term)
            for i in range(len(words) - len(target) + 1):
                if target and words[i:i + len(target)] == target:
                    spans.append((i, i + len(target)))
        return spans

    # The paraphrase rule (X06): a cue phrase and a person reference in one sentence.

    def paraphrase(self):
        sentences = {}
        for token in self.tokens:
            sentences.setdefault(token.sentence, []).append(token)
        for sentence in sentences.values():
            words = [t.word for t in sentence]
            cues = []
            for i, word in enumerate(words):
                for group, phrase in cue_index().get(word, ()):
                    if tuple(words[i:i + len(phrase)]) == phrase:
                        cues.append((group, i, i + len(phrase)))
            if not cues:
                continue
            used = {k for _, a, b in cues for k in range(a, b)}
            people = [t for i, t in enumerate(sentence) if i not in used and self.person(sentence, i)]
            if not people:
                continue
            cues.sort(key=lambda c: (c[1], -(c[2] - c[1])))
            kept = []
            for group, a, b in cues:
                if any(g == group and x <= a and b <= y for g, x, y in kept):
                    continue
                kept.append((group, a, b))
            who = self.text[people[0].start:people[0].end]
            for group, a, b in kept:
                self.hit("paraphrase", group, "block", sentence[a].start, sentence[b - 1].end,
                         "a remark about a person (%s): the cue %r beside %r" %
                         (group, self.text[sentence[a].start:sentence[b - 1].end], who),
                         "the point made about the work, with no person's stakes, health, plans or standing")

    def person(self, sentence, index):
        token = sentence[index]
        if token.word in ROLE_SINGLE:
            return True
        if index + 1 < len(sentence) and (token.word, sentence[index + 1].word) in ROLE_PAIRS:
            return True
        return token.cap and not token.first and not token.word.isdigit() and token.word not in COMMON_WORDS and \
            token.word not in PRONOUNS and token.word not in STOP_WORDS

    # Figures, split renderings, numbers and split ids (X25, X34, Y02, Y08).

    def figure_pools(self):
        sets = self.sets
        keep = [e for e in sets.cost if self.usable(e[2:])], [e for e in sets.cost_percent if self.usable(e[2:])], \
            [e for e in sets.record if self.usable(e[2:])], [e for e in sets.record_percent if self.usable(e[2:])]
        return keep

    def numbers(self):
        if self.unit.structural:
            return
        summary = self.unit.mode == "summary"
        cost, cost_percent, record, record_percent = self.figure_pools()
        exclusions = self.run.exclusions.figures
        text = self.vf.text
        dates = date_spans(text)
        chains = [] if self.unit.kind == "number" else digit_chains(text, dates)
        date_chains = [(c[0][0], c[-1][1]) for c in chains if chain_is_date(text, c)]
        reported = set()
        for chain in chains:
            start, end = self.vf.span(chain[0][0], chain[-1][1])
            if chain_is_date(text, chain):
                self.hit("split-figure", None, "warn", start, end, "a date written with its digits split",
                         "the date written whole, such as 2026-11-03")
                continue
            value = Fraction(int("".join(text[s:e] for s, e in chain)))
            self.split_match(value, Fraction(1), start, end, cost, record, exclusions)
        for variant_index, variant in enumerate([self.vf] + ([self.vfd] if self.vfd else [])):
            for number in parse_numbers(variant, self.text):
                start, end = variant.span(number.start, number.end)
                if variant_index == 0 and overlaps(date_chains, number.start, number.end):
                    continue
                if number.split:
                    self.split_match(number.value, number.precision, start, end, cost, record, exclusions)
                    continue
                if summary:
                    continue
                key = (start, number.value)
                if key in reported:
                    continue
                reported.add(key)
                in_link = inside(self.links, number.start, number.end) if variant_index == 0 else True
                self.classify(number, start, end, in_link or variant_index > 0, cost, cost_percent, record,
                              record_percent, exclusions)

    def split_match(self, value, precision, start, end, cost, record, exclusions):
        probe = Number(value, precision, 0, 0)
        for figure, fprec, where, _ in exclusions:
            if probe.matches(figure, fprec):
                self.hit("split-figure", None, "block", start, end, "an excluded figure written in split form (%s)" %
                         where, "the text without the figure", where.split(" line ")[0])
                return
        for figure, fprec, file, _ in cost:
            if probe.matches(figure, fprec):
                self.hit("split-figure", None, "block", start, end, "the client figure %s written in split form" %
                         show(figure), "the text without the client's figure", file)
                return
        for figure, fprec, file, _ in record:
            if probe.matches(figure, fprec):
                self.hit("split-figure", None, "warn", start, end, "a number of the client record written in split "
                         "form", "check it is meant for the client; it is reported and kept", file)
                return

    def classify(self, number, start, end, in_link, cost, cost_percent, record, record_percent, exclusions):
        for figure, fprec, where, _ in exclusions:
            if number.matches(figure, fprec):
                self.hit("exclusion", "figure", "block", start, end, PROBLEMS["exclusion"][0] % ("figure", where),
                         PROBLEMS["exclusion"][1], where.split(" line ")[0])
                break
        quiet = in_link or (number.plain and number.value >= 10 ** 7)
        if number.percent:
            for figure, fprec, file, _ in cost_percent:
                if number.matches(figure, fprec):
                    return self.hit("figure", None, "block", start, end, "matches the client's cost percentage %s%% "
                                    "(%s)" % (show(figure), file), "the text without the client's figure", file)
            if number.value < 10 or quiet:
                return None
            for figure, fprec, file, _ in record_percent:
                if number.matches(figure, fprec):
                    return self.record_warning(start, end, file)
            return self.number_warning(start, end)
        matched = [f for f in cost if number.matches(f[0], f[1])]
        large = [f for f in matched if f[0] >= 1000]
        if large:
            return self.hit("figure", None, "block", start, end, "matches the client's cost figure %s (%s)" %
                            (show(large[0][0]), large[0][2]), "the text without the client's figure", large[0][2])
        if matched and (number.cue or number.currency or number.rate):
            return self.hit("figure", None, "block", start, end, "matches the client's cost figure %s beside a cost "
                            "word (%s)" % (show(matched[0][0]), matched[0][2]), "the text without the client's figure",
                            matched[0][2])
        if quiet or number.value < 10:
            return None
        if matched:
            return self.record_warning(start, end, matched[0][2], "matches a client figure with no cost word beside it")
        for figure, fprec, file, _ in record:
            if number.matches(figure, fprec):
                return self.record_warning(start, end, file)
        return self.number_warning(start, end)

    def record_warning(self, start, end, file, problem="matches a number of the client record"):
        self.hit("record-number", None, "warn", start, end, problem + " (%s)" % file,
                 "flag, do not remove: check it is meant for the client", file)

    def number_warning(self, start, end):
        self.hit("number", None, "warn", start, end, "a number that matches no figure of the client record",
                 "check the number is meant for the client")

    def split_ids(self):
        if self.unit.structural or self.unit.kind == "number":
            return
        text = self.vf.text
        for chain in id_chains(text):
            s, e = chain[0][0], chain[-1][1]
            if chain_is_date(text, chain) or inside(self.links, s, e):
                continue
            start, end = self.vf.span(s, e)
            self.hit("term", "id-patterns", "block", start, end, "an id or a phone number written in digit groups "
                     "(split id, X34)", PROBLEMS["term"][1])

    # The tool-category assertion (X12).

    def tool_categories(self):
        if not self.counted:
            return
        text = self.vf.text
        sentences = sentence_spans(text)
        starts = [s for s, _ in sentences]
        by_sentence = {}
        for cls, fs, fe, start, end in self.counted:
            index = max(0, bisect.bisect_right(starts, fs) - 1)
            by_sentence.setdefault(index, []).append((cls, start, end, fs))
        for index, hits in sorted(by_sentence.items()):
            if len({h[0] for h in hits}) < 3:
                continue
            paragraph = self.paragraph_of(hits[0][3])
            if any(self.proper(t) for t in self.tokens if t.paragraph == paragraph):
                continue
            hits.sort(key=lambda h: h[1])
            self.hit("tool-categories", None, "block", hits[0][1], hits[0][2], "names %d tool categories in one "
                     "sentence of a paragraph with no proper noun" % len({h[0] for h in hits}),
                     "two categories at most in a sentence, or the client's own tool names")

    def paragraph_of(self, fstart):
        spans = paragraph_spans(self.vf.text)
        starts = [s for s, _ in spans]
        return max(0, bisect.bisect_right(starts, fstart) - 1)

    def proper(self, token):
        words = self.lists.category_words
        if token.cap and not token.first and token.word != "i" and token.word not in COMMON_WORDS and \
                token.word not in words and token.word not in PRODUCT_WORDS and not token.word.isdigit():
            return True
        return token.upper and 2 <= len(token.word) <= 6 and token.word.isalpha() and token.word not in words and \
            token.word not in STOP_WORDS and token.word not in PRODUCT_WORDS

    # Quotes, copied runs and near copies (X19, X24, X36, X37).

    def runs_and_quotes(self):
        words = [t.word for t in self.tokens]
        sets, summary = self.sets, self.unit.mode == "summary"
        covered = set()
        for a, b, file in stretches(self.grams(words, QUOTE_WORDS, lambda g: [
                e[0] for e in sets.quotes.get(g, ()) if self.usable(e)])):
            covered.update(range(a, b))
            self.hit("quote", None, "block", self.tokens[a].start, self.tokens[b - 1].end, "eight or more words of a "
                     "client quote (%s)" % file, "the point in new words: a client's own words stay in the record",
                     file)
        if self.unit.mode == "client-safe-block":
            return

        def runs_usable(entry):
            return self.usable(entry) and not (summary and SUMMARY_FILE.fullmatch(entry[0]))

        def exact(gram):
            if distinct(gram) < RUN_MIN_DISTINCT:
                return []
            entries = [e for e in sets.runs.get(gram, ()) if runs_usable(e)]
            if not entries:
                return []
            conflict = [e for e in entries if e[2]]
            if conflict:
                return [conflict[0][0]]
            if any(self.usable(e) for e in sets.docs.get(gram, ())):
                return []
            return [entries[0][0]]

        for a, b, file in stretches(self.grams(words, RUN_WORDS, exact)):
            if any(k in covered for k in range(a, b)):
                continue
            covered.update(range(a, b))
            self.hit("copied-run", None, "block", self.tokens[a].start, self.tokens[b - 1].end, "six or more words "
                     "copied from an internal file (%s)" % file, "new words: internal text never reaches the client",
                     file)
        if len(words) < NEAR_WORDS:
            return
        near_runs, near_docs = sets.near("runs"), sets.near("docs")

        def near(gram):
            if distinct(gram) < RUN_MIN_DISTINCT:
                return []
            keys = [(p,) + gram[:p] + gram[p + 1:] for p in range(NEAR_WORDS)]
            entries = [e for k in keys for e in near_runs.get(k, ()) if runs_usable(e)]
            if not entries:
                return []
            conflict = [e for e in entries if e[2]]
            if conflict:
                return [conflict[0][0]]
            if any(self.usable(e) for k in keys for e in near_docs.get(k, ())):
                return []
            return [sorted(entries)[0][0]]

        for a, b, file in stretches(self.grams(words, NEAR_WORDS, near)):
            if any(k in covered for k in range(a, b)):
                continue
            self.hit("copied-run", None, "block", self.tokens[a].start, self.tokens[b - 1].end, "eight words that "
                     "match an internal file's in seven places (%s)" % file, "new words: internal text never reaches "
                     "the client", file, near=True)

    @staticmethod
    def grams(words, size, lookup):
        found = []
        for i in range(len(words) - size + 1):
            result = lookup(tuple(words[i:i + size]))
            if result:
                found.append((i, i + size, result[0]))
        return found

    def execute(self):
        unit, mode = self.unit, self.unit.mode
        if unit.kind == "number":
            self.numbers()
            self.seller_ids()
            return self.hits
        self.literals()
        if mode != "summary":
            self.regex_rows()
            self.notes_and_credentials()
            self.seller_ids()
            self.phonetic()
            self.paraphrase()
            self.split_ids()
        self.numbers()
        self.tool_categories()
        self.runs_and_quotes()
        if mode != "summary":
            self.hits += wall_hits(self.run, self)
        return self.hits


SUMMARY_FILE = re.compile(r"strands/\d{3}-[^/]+/SUMMARY\.md")
_CUES = {}


def cue_index():
    """{first word: [(group, phrase words)]} of the paraphrase cues, longest phrases first."""
    if not _CUES:
        for group, phrases in PARAPHRASE_CUES:
            for phrase in phrases:
                words = tuple(words_of(phrase))
                _CUES.setdefault(words[0], []).append((group, words))
        for value in _CUES.values():
            value.sort(key=lambda item: -len(item[1]))
    return _CUES


ROLE_SINGLE = frozenset(r for r in ROLE_WORDS if " " not in r)
ROLE_PAIRS = frozenset(tuple(r.split()) for r in ROLE_WORDS if " " in r)


def distinct(gram):
    return sum(1 for word in gram if word.isdigit() or word not in COMMON_WORDS)


def stretches(found):
    """Overlapping or adjacent windows merged into maximal stretches, each named by its first window's source."""
    merged = []
    for start, end, source in found:
        if merged and start <= merged[-1][1] - 1:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]), merged[-1][2])
        else:
            merged.append((start, end, source))
    return merged


def windows(size):
    """X42: a line longer than 10,000 characters is read in windows of 10,000 overlapping by 200."""
    if size <= LINE_WINDOW:
        return [(0, size)]
    return [(begin, min(size, begin + LINE_WINDOW)) for begin in range(0, size, LINE_WINDOW - LINE_OVERLAP)]


def show(value):
    value = Fraction(value)
    if value.denominator == 1:
        return "{:,}".format(int(value))
    return "{:,}".format(float(value))


# The cross-client wall (X01, X21, X27, X30) is part 2's. Until it is built, a home that holds another client
# record or an index stops every check that would run it, so a payload never passes the wall unchecked.

def wall_guard(run):
    others = 0
    for folder in ("clients", "archive"):
        base = run.home / folder
        try:
            entries = sorted(base.iterdir()) if base.is_dir() else []
        except OSError as exc:
            raise cannot("<home>/%s/" % folder, WHOLE, "cannot list the folder: %s" % exc, "a readable home")
        for entry in entries:
            try:
                same = entry.resolve() == run.root
            except OSError:
                same = False
            if not same and entry.is_dir() and (entry / "CLIENT.md").is_file():
                others += 1
    if others or (run.home / "clients-index.json").exists():
        raise cannot("<home>/clients-index.json", "wall", "the cross-client wall is not built in this version of the "
                     "lint, and the home holds %d other client record(s) or an index, so it cannot check them"
                     % others, "the lint with its wall built; until then a check in this home stops here")


def wall_hits(run, check):
    """The wall's findings for one unit; part 2 replaces this. Here it only proves there is nothing to see."""
    if not run.wall_checked:
        wall_guard(run)
        run.wall_checked = True
    return []


def finding(run, unit, text, rule, cls, severity, start, end, problem, expected, source, extra):
    field, line, column = unit.where(start)
    found = {"file": unit.file, "field": field, "problem": problem, "expected": expected, "rule": rule, "class": cls,
             "severity": severity, "line": line, "column": column, "match": cut(text[start:end]), "source": source}
    if unit.part:
        found["part"] = unit.part
    found.update(extra)
    found["_start"], found["_end"] = start, end
    found["_order"] = (0, unit.seq, start, rule, cls or "", found["match"] or "")
    return found


CONTAINED = ("term", "exclusion", "seller-account", "internal-note", "credential", "paraphrase", "split-figure")


def check_unit(run, unit):
    """Every rule the unit's mode runs, the findings deduplicated, then the strand's allowlist applied."""
    check = Check(run, unit)
    hits = check.execute()
    findings, seen = [], set()
    for rule, cls, severity, start, end, problem, expected, source, extra in hits:
        key = (rule, cls, start, end)
        if key in seen or end <= start:
            continue
        seen.add(key)
        findings.append(finding(run, unit, check.text, rule, cls, severity, start, end, problem, expected, source,
                                extra))
    kept = []
    for f in findings:
        if f["rule"] in CONTAINED and any(
                g is not f and g["rule"] == f["rule"] and g["class"] == f["class"] and g["_start"] <= f["_start"] and
                f["_end"] <= g["_end"] and (g["_end"] - g["_start"]) > (f["_end"] - f["_start"]) for g in findings):
            continue
        kept.append(f)
    kept = apply_allowlist(run, unit, check.text, kept)
    for f in kept:
        if run.spans and f["severity"] == "block" and "_start" in f:
            start, end = unit.raw_span(f["_start"], f["_end"])
            f["span"] = {"start": start, "end": end}
        run.add(f)


def apply_allowlist(run, unit, text, findings):
    """X10, X39, Y06: a row of the strand's own allowlist with the user's ok clears a vocabulary term or a
    paraphrase cue to a caution; a row that meets anything else leaves the block and warns once per finding."""
    rows = load_allowlist(run, unit.strand)
    if not rows:
        return findings
    extra = []
    for f in findings:
        if f["severity"] != "block":
            continue
        target = normal_form(text[f["_start"]:f["_end"]])
        matched = [r for r in rows if r.normal and r.normal == target]
        if not matched:
            continue
        if f["rule"] in ("term", "paraphrase") and f["class"] in CLEARABLE:
            granted = [r for r in matched if r.ok]
            if granted:
                f["severity"], f["cleared_by"] = "caution", "%s line %d" % (granted[0].file, granted[0].line)
                f["problem"] += "; kept as the client's own word"
                f["expected"] = "nothing: the strand's allowlist keeps it, with the user's ok"
            continue
        what = "%s of class %s" % (f["rule"], f["class"]) if f["class"] else f["rule"]
        for row in matched:
            warn = record_warning(row.file, row.line, "this row names a %s finding in %s %s; this class is never "
                                  "cleared by an allowlist" % (what, f["file"], f["field"]),
                                  "the text changed; the row clears nothing here", "allowlist")
            warn["match"] = cut(row.term)
            extra.append(warn)
    return findings + extra


# Inputs: what a command checks, as units (X08, X22, X35, X38).

def inside_record(run, value, flag):
    """(record-relative POSIX name, resolved path) of a path the session hands, which must lie inside the record."""
    if os.path.isabs(value):
        path = Path(value)
    else:
        path = run.root.joinpath(*[p for p in value.replace("\\", "/").split("/") if p not in ("", ".")] or ["."])
    resolved = Path(os.path.realpath(str(path)))
    try:
        rel = resolved.relative_to(Path(os.path.realpath(str(run.root)))).as_posix()
    except ValueError:
        raise cannot(value.replace("\\", "/"), flag, "the path lies outside the record", "a path inside the record, "
                     "so every finding names a record-relative file")
    if not resolved.exists():
        raise cannot(rel, flag, "no such file or folder in the record", "a file the session wrote")
    return rel, resolved


def path_strand(rel):
    match = re.match(r"strands/(\d{3})-[^/]+(?:/|$)", rel)
    return match.group(1) if match else None


def scan_targets(run, paths, flag):
    """[(record-relative name, path)] in the order given, a folder's files in sorted POSIX path order (X35)."""
    if not paths:
        folders = []
        for folder in strand_folders(run):
            if flag and not folder.name.startswith(flag + "-"):
                continue
            for sub in (("drafts",), ("deliverables", "handoff")):
                candidate = folder.joinpath(*sub)
                if candidate.is_dir():
                    folders.append(run.name(candidate))
        paths = folders
    targets = []
    for value in paths:
        rel, path = inside_record(run, value, "path")
        if path.is_dir():
            found = []

            def failed(exc):
                raise cannot(rel, WHOLE, "cannot list the folder: %s" % exc, "a readable folder")

            for folder, dirs, files in os.walk(str(path), onerror=failed):
                dirs.sort()
                for name in files:
                    found.append(Path(folder) / name)
            for item in sorted(found, key=lambda p: Path(os.path.realpath(str(p))).as_posix()):
                if item.name.lower() in SYSTEM_FILES:
                    continue
                targets.append(target_of(run, item))
        else:
            targets.append(target_of(run, path))
    for rel, _, _ in targets:
        strand = path_strand(rel)
        if flag and strand and strand != flag:
            raise cannot(rel, "--strand", "the path is in strand %s, not %s" % (strand, flag),
                         "--strand left out, or the strand the path is in")
    return targets


def target_of(run, path):
    resolved = Path(os.path.realpath(str(path)))
    try:
        rel = resolved.relative_to(Path(os.path.realpath(str(run.root)))).as_posix()
    except ValueError:
        raise cannot(Path(path).name, "path", "a file in the folder resolves outside the record",
                     "files inside the record only")
    if os.path.splitext(rel)[1].lower() not in SCAN_EXT:
        raise cannot(rel, WHOLE, "the lint cannot read this kind of file", "a file the lint can read (.md, .txt, "
                     ".docx, .json); move this one out of the folder or convert it")
    return rel, resolved, path_strand(rel)


def scan_mode(rel, text):
    if re.fullmatch(r"strands/\d{3}-[^/]+/SUMMARY\.md", rel):
        return "summary"
    if rel.lower().endswith(".md") and (rel.startswith("calls/") or (rel.startswith("inputs/") and is_snapshot(text))):
        return "client-safe-block"
    return "full"


def file_units(run, rel, path, strand, seq):
    """(mode, units) of one scanned file."""
    ext = os.path.splitext(rel)[1].lower()
    if ext == ".docx":
        units = []
        for index, (part, lines, labels) in enumerate(docx_text(run, path, rel)):
            units.append(Unit(rel, "\n".join(lines), (seq, index), part=part, strand=strand, labels=labels))
        return "full", units
    if ext == ".json":
        data = json_value(decode(run.read(path, rel, PAYLOAD_LIMIT), rel)[0], rel)
        return "full", payload_units(rel, data, strand, seq)
    text, raw = decode(run.read(path, rel), rel)
    mode = scan_mode(rel, text)
    if mode != "client-safe-block":
        return mode, [Unit(rel, text, (seq, 0), strand=strand, mode=mode, raw=raw)]
    lines = text.split("\n")
    inside_lines, problem = block_lines(lines, BLOCK_MARKS[0], BLOCK_MARKS[1])
    if problem:
        raise cannot(rel, "line %d" % problem[0], "the client-safe marks are not well formed: %s" % problem[1],
                     "an opening and a closing mark, each alone on its line, so the lint can tell what is client-safe")
    if not inside_lines and not any(line.strip() == BLOCK_MARKS[0] for line in lines):
        run.add(record_warning(rel, 1, "no client-safe block in this file", "the call summary or snapshot with its "
                               "marked client-safe block"))
        return mode, []
    kept = "\n".join(line if index in inside_lines else " " * len(line) for index, line in enumerate(lines))
    return mode, [Unit(rel, kept, (seq, 0), strand=strand, mode=mode, raw=raw)]


def payload_units(file, data, strand, seq):
    """X22, Y08: every string, every object key and every number at every depth, a string holding JSON walked as
    JSON as well; a digit-only value under a structural id key is marked structural. The walk is iterative."""
    units, stack, count = [], [("$", data, 1, False)], 0
    while stack:
        path, value, depth, structural = stack.pop()
        if depth > DEPTH_LIMIT:
            raise cannot(file, path, "the payload is nested deeper than %d levels" % DEPTH_LIMIT,
                         "a tool input of ordinary depth")
        count += 1
        if isinstance(value, dict):
            pushed = []
            for key, sub in value.items():
                key = str(key)
                sub_path = path + ("." + key if SIMPLE_KEY.fullmatch(key) else "[%s]" % json.dumps(key,
                                                                                                    ensure_ascii=False))
                units.append(Unit(file, key, (seq, len(units)), field=sub_path + "<key>", strand=strand,
                                  kind="payload"))
                if key in STRUCTURAL_ID_KEYS and isinstance(sub, list):
                    for index, item in enumerate(sub):
                        pushed.append(("%s[%d]" % (sub_path, index), item, depth + 1, is_structural(item)))
                    continue
                pushed.append((sub_path, sub, depth + 1, key in STRUCTURAL_ID_KEYS and is_structural(sub)))
            stack.extend(reversed(pushed))
        elif isinstance(value, list):
            stack.extend(reversed([("%s[%d]" % (path, i), item, depth + 1, False) for i, item in enumerate(value)]))
        elif isinstance(value, str):
            units.append(Unit(file, value, (seq, len(units)), field=path, strand=strand, kind="payload",
                              structural=structural))
            stripped = value.strip()
            if stripped[:1] in ("{", "["):
                try:
                    inner = json.loads(stripped)
                except ValueError:
                    inner = None
                if isinstance(inner, (dict, list)):
                    stack.append((path + "<json>", inner, depth + 1, False))
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            text = str(value) if isinstance(value, int) else repr(value)
            units.append(Unit(file, text, (seq, len(units)), field=path, strand=strand, kind="number",
                              structural=structural))
    return units


def is_structural(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value > 0
    return isinstance(value, str) and bool(STRUCTURAL_VALUE.fullmatch(value))


# The commands (X08). Each returns its exit code; the run carries what the envelope prints.

def prepare(run):
    load_lists(run)
    run.exclusions = load_exclusions(run)
    run.sets = build_sets(run)


def cmd_scan(run):
    run.locate()
    flag = run.args.strand
    if flag is not None:
        strand_folder(run, flag)
    targets = scan_targets(run, run.args.paths, flag)
    prepare(run)
    modes, strands = [], set()
    for seq, (rel, path, strand) in enumerate(targets):
        mode, units = file_units(run, rel, path, strand, seq)
        modes.append(mode)
        strands.add(strand or flag)
        if mode in ("summary", "client-safe-block") and rel in run.inputs:
            run.inputs[rel]["mode"] = mode
        for unit in units:
            check_unit(run, unit)
    run.mode = modes[0] if modes and len(set(modes)) == 1 else (None if modes else "full")
    run.strand = strands.pop() if len(strands) == 1 else (flag if not strands else None)
    return outcome(run)


def cmd_payload(run):
    run.locate()
    args = run.args
    strand_folder(run, args.strand)
    run.strand = args.strand
    rel, path = inside_record(run, args.file, "--file")
    if not path.is_file():
        raise cannot(rel, "--file", "the payload is not a file", "the tool input written as one JSON file")
    data = json_value(decode(run.read(path, rel, PAYLOAD_LIMIT), rel)[0], rel)
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    run.args_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    prepare(run)
    units = payload_units(rel, data, args.strand, 0)
    wall_hits(run, None)
    for unit in units:
        check_unit(run, unit)
    return outcome(run)


def cmd_not_built(run):
    raise cannot("leak_lint.py", run.command, "the %s command is not built yet" % run.command,
                 "a later build of leak_lint.py; until then this command stops and never passes")


COMMANDS = {"scan": cmd_scan, "payload": cmd_payload, "blueprint": cmd_not_built, "wall": cmd_not_built,
            "terms": cmd_not_built, "index": cmd_not_built}
EXIT_VERDICT = {0: VERDICTS[0], 1: VERDICTS[2], 2: VERDICTS[1], 3: VERDICTS[3]}


def outcome(run):
    severities = {f["severity"] for f in run.findings}
    return 1 if "block" in severities else (2 if severities else 0)


def envelope(run, code):
    data = {"ok": code in (0, 2), "command": run.command, "verdict": EXIT_VERDICT[code]}
    if run.command in ("scan", "blueprint"):
        data["mode"] = run.mode
    data["strand"] = run.strand
    data["inputs"] = [run.inputs[name] for name in sorted(run.inputs)]
    if run.command == "payload":
        data["args_digest"] = run.args_digest
    findings = sorted(run.findings, key=lambda f: f["_order"])
    data["findings"] = [{k: v for k, v in f.items() if not k.startswith("_")} for f in findings]
    data["counts"] = {severity: sum(1 for f in findings if f["severity"] == severity) for severity in SEVERITIES}
    if code == 3:
        data["error"] = run.error
    return data


def full_error(found):
    """Every part of the error non-empty (L27)."""
    defaults = {"file": "leak_lint.py", "field": WHOLE, "problem": "the lint could not run", "expected": "a run that "
                "finishes"}
    return {key: (str(found.get(key)) if found.get(key) not in (None, "") else defaults[key]) for key in KEYS}


def build_parser():
    parser = Parser(prog="leak_lint.py", description="The leak lint.", add_help=False)
    parser.add_argument("--record", help="the client folder (default: the current folder)")
    top = parser.add_subparsers(dest="command", metavar="command", parser_class=Parser)
    top.required = True
    scan = top.add_parser("scan", add_help=False)
    scan.add_argument("--strand")
    scan.add_argument("--spans", action="store_true")
    scan.add_argument("paths", nargs="*")
    payload = top.add_parser("payload", add_help=False)
    payload.add_argument("--strand", required=True)
    payload.add_argument("--kind", required=True, choices=KINDS)
    payload.add_argument("--file", required=True)
    payload.add_argument("--spans", action="store_true")
    blueprint = top.add_parser("blueprint", add_help=False)
    blueprint.add_argument("--strand", required=True)
    blueprint.add_argument("--spans", action="store_true")
    wall = top.add_parser("wall", add_help=False)
    wall.add_argument("--text", required=True)
    terms = top.add_parser("terms", add_help=False)
    terms.add_argument("folder")
    top.add_parser("index", add_help=False)
    return parser


def main(argv=None):
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except Usage as exc:
        emit({"ok": False, "command": None, "verdict": VERDICTS[3], "inputs": [], "findings": [],
              "counts": {severity: 0 for severity in SEVERITIES},
              "error": dict(zip(KEYS, ("leak_lint.py", "arguments", str(exc), parser.format_usage().strip())))})
        return 3
    run = Run(args.command, args)
    try:
        handler = COMMANDS[args.command]
        code = handler(run)
    except mc.MMBError as exc:  # a refusal of mmb_common is still "could not run" here: exit 1 means a leak only
        run.error, code = full_error(exc.findings[0] if exc.findings else {}), 3
    except Exception as exc:  # G10, L205: anything unexpected is "could not run", still one JSON object
        run.error, code = full_error({"file": "leak_lint.py", "field": type(exc).__name__, "problem": str(exc) or
                                      "an internal error with no message", "expected": "a run without an internal "
                                      "error"}), 3
    emit(envelope(run, code))
    return code


if __name__ == "__main__":
    sys.exit(main())
