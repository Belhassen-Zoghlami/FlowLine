import re 
from dataclasses import dataclass
from pathlib import Path

ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]") #find terminal color codes
TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\s*" #find timestamps at the beginning of log lines (YYYY-MM-DDTHH:MM:SS(.SSS)Z)
)
COMMAND_RE = re.compile(
    r"^\s*##\[(?:error|warning|debug|group|endgroup|command|section)\]", #find github workflow markers (##[error], ##[warning], ##[group]..)
    re.IGNORECASE,
)
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE) #find urls
PATH_RE = re.compile(r"(?<!\w)(?:[A-Za-z]:\\|/)[^\s:]+") #find absolute paths
FILE_RE = re.compile(
    r"\b[\w.-]+\.(?:"
    r"py|pyi|js|jsx|mjs|cjs|ts|tsx|vue|svelte|astro|"
    r"java|kt|kts|scala|groovy|gradle|"
    r"go|rs|rb|php|cs|fs|fsx|vb|"
    r"c|cc|cpp|cxx|h|hpp|hh|m|mm|swift|lua|"
    r"pl|pm|r|dart|ex|exs|erl|hrl|clj|"
    r"sh|bash|zsh|ps1|"
    r"yml|yaml|json|toml|xml|csproj|sln|props|targets|"
    r"lock|mod|sum|proto|sql|md|rst|txt"
    r")(?::\d+)?\b",
    re.IGNORECASE, #find file names with common extensions (+ if line numbers)
)
HASH_RE = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE) #find git commit hashes
NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b") #find numbers
SPACE_RE = re.compile(r"\s+") #find space characters
NOISE_RE = re.compile(r"process completed with exit code", re.IGNORECASE) #find non useful noise lines in logs

# > a data class is a simple way to store data in a class without having to write boilerplate code for init, repr, etc. <
#frozen= true means its immutable after creation
@dataclass(frozen=True) #data class is used to store the result of parsing a log
class ParseResult:
    signature: str
    failed_step:str
    is_parsed:bool

@dataclass(frozen=True) #data class used to store a failure rule (name n pattern)
class FailureRule:
    name:str
    pattern:re.Pattern

# a tuple of failure rules, each rule is a FailureRule object with a name and a pattern
RULES = tuple( 
    FailureRule(name, re.compile(pattern, re.IGNORECASE))
    for name, pattern in (
        ("python-import", r"ModuleNotFoundError:\s*No module named"),
        ("python-import", r"\bImportError:\s*"),
        ("python-syntax", r"\b(?:SyntaxError|IndentationError|TabError):\s*"),
        ("node-module", r"\bCannot find module\b"),
        ("node-module", r"\bModule not found\b"),
        ("node-package-manager", r"^\s*(?:npm|yarn|pnpm)\s+(?:ERR!|error)(?:\s|$)"),
        ("node-package-manager", r"\bERR_PNPM_[A-Z_]+\b"),
        ("node-package-manager", r"^\s*error\s+Command failed\b"),
        ("typescript", r"\berror\s+TS\d+"),
        ("python-packaging", r"(?:Could not find a version|No matching distribution|Failed building wheel)"),
        ("gradle", r"\bFAILURE:\s*Build failed"),
        ("gradle", r"\bCould not resolve (?:all files|dependencies)\b"),
        ("java", r"^\s*Exception in thread\b"),
        ("dotnet", r"\berror\s+CS\d+"),
        ("dotnet", r"^\s*Unhandled exception\b"),
        ("go", r"^\s*panic:\s*"),
        ("go", r"^\s*---\s+FAIL:\s*"),
        ("go", r"\bcannot find package\b|\bundefined:"),
        ("rust", r"^\s*error\[[A-Z]+\d+\]:\s*"),
        ("rust", r"\bpanicked at\b"),
        ("rust", r"\bcould not compile\b"),
        ("compiler", r"^\s*\S+:\d+:\d+:\s+(?:fatal\s+)?error:\s*"),
        ("eslint", r"^\s*\S+:\d+:\d+:\s+error\s+"),
        ("c-cpp", r"^\s*fatal error:\s*"),
        ("c-cpp", r"\b(?:undefined reference|linker command failed|ld returned|Segmentation fault)\b"),
        ("make", r"^\s*make(?:\[\d+\])?:\s+\*\*\*"),
        ("cmake", r"^\s*CMake Error\b"),
        ("ruby", r"\b(?:LoadError|NameError|NoMethodError):\s*"),
        ("ruby", r"\brake aborted!"),
        ("ruby", r"^\s*Failure/Error:\s*"),
        ("php", r"\b(?:Fatal error|Parse error|Uncaught)\b"),
        ("shell", r"\bcommand not found\b"),
        ("docker", r"\bERROR:\s*failed to solve\b"),
        ("docker", r"\bdocker:\s*Error\b"),
        ("python-linter", r"^\s*\S+\.py:\d+:\d+:\s+[A-Z]\d+"),
        ("test", r"^\s*FAILED\s+\S+"),
        ("test", r"^\s*FAIL\s+\S+"),
        ("test", r"\bAssertionError\b"),
        ("timeout", r"\b(?:timeout|timed out|time limit exceeded|deadline exceeded|took too long)\b"),
        ("exception", r"\b[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception):\s*"),
        ("maven", r"^\s*\[ERROR\]\s*"),
        ("generic-error", r"\b(?:ERROR|error):\s*"),
    )
)

ROOT_ERROR_PATTERNS = tuple(rule.pattern for rule in RULES) 

def normalize_signature(text):
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    text = text or ""
    text = ANSI_RE.sub("", text)
    text = TIMESTAMP_RE.sub("", text)
    text = COMMAND_RE.sub("", text).strip()
    text = URL_RE.sub("<url>", text)
    text = PATH_RE.sub("<path>", text)
    text = FILE_RE.sub("<path>", text)
    text = HASH_RE.sub("<hash>", text)
    text = NUMBER_RE.sub("<n>", text)
    text = SPACE_RE.sub(" ", text).strip().lower()
    return text[:500]


def step_name(entry_name):
    name = str(entry_name or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"\.(?:txt|log)$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"^\d+[_-]?", "", name).strip()
    name = name.replace("_", " ").strip()
    return name[:255]


def _clean_line(line):
    line = ANSI_RE.sub("", line)
    line = TIMESTAMP_RE.sub("", line)
    line = COMMAND_RE.sub("", line).strip()
    return line


def _is_noise(line):
    return bool(NOISE_RE.search(line))


def parse_entries(entries):
    best = None
    fallback = None

    for entry_name, text in entries:
        step = step_name(entry_name)
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="replace")

        for raw in (text or "").splitlines():
            line = _clean_line(raw)
            if not line or _is_noise(line):
                continue

            for rank, rule in enumerate(RULES):
                if rule.pattern.search(line):
                    if best is None or rank < best[0]:
                        best = (rank, line, step)
                    break

            if "##[error]" in raw.lower() and fallback is None:
                fallback = (line, step)

    if best is not None:
        signature = normalize_signature(best[1])
        if signature:
            return ParseResult(signature, best[2], True)

    if fallback is not None:
        signature = normalize_signature(fallback[0])
        if signature:
            return ParseResult(signature, fallback[1], True)

    return ParseResult("", "", False)

