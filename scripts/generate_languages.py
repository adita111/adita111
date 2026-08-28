import os
import json
import urllib.request
import urllib.parse
from collections import defaultdict
from datetime import datetime, timedelta, timezone


USERNAME = "adita111"

# Repo-uri pe care NU vrem să le luăm în calcul.
EXCLUDED_REPOS = {
    "adita111/Aplicatie-ASP-NET-citire-grade",
}

# Limbaje pe care nu vrem să le afișăm deloc.
HIDDEN_LANGUAGES = {
    "C",
}

# Dacă vrei să incluzi manual repo-uri private din organizații,
# le pui aici:
#
# "NumeOrganizatie/NumeRepo"
#
EXTRA_REPOS = [
     "code4ulbs/platacuora",
]

# Câte limbaje maxime să apară.
MAX_LANGUAGES = 7

# Commit chart: ultima perioadă analizată.
COMMIT_DAYS = 365


TOKEN = os.environ.get("GH_PAT")

if not TOKEN:
    raise RuntimeError("GH_PAT was not provided.")


API = "https://api.github.com"


def github_request(path):
    request = urllib.request.Request(
        API + path,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USERNAME,
        },
    )

    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def get_user_repositories():
    repos = []
    page = 1

    while True:
        data = github_request(
            f"/user/repos?per_page=100&page={page}"
            "&affiliation=owner"
            "&sort=updated"
        )

        if not data:
            break

        repos.extend(data)
        page += 1

    repo_names = {
        repo["full_name"]
        for repo in repos
        if repo["full_name"] not in EXCLUDED_REPOS
        and not repo.get("fork", False)
    }

    repo_names.update(EXTRA_REPOS)

    return sorted(repo_names)


def get_languages(repo):
    owner, name = repo.split("/", 1)

    try:
        return github_request(
            f"/repos/{owner}/{name}/languages"
        )
    except Exception as e:
        print(f"Could not get languages for {repo}: {e}")
        return {}


def aggregate_repo_languages(repos):
    totals = defaultdict(int)

    for repo in repos:
        print(f"Reading languages: {repo}")

        languages = get_languages(repo)

        for language, amount in languages.items():
            if language not in HIDDEN_LANGUAGES:
                totals[language] += amount

    return totals


EXTENSION_LANGUAGE = {
    ".rb": "Ruby",
    ".erb": "Ruby",
    ".rake": "Ruby",

    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",

    ".ts": "TypeScript",
    ".tsx": "TypeScript",

    ".java": "Java",

    ".py": "Python",

    ".cs": "C#",

    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".hxx": "C++",

    ".html": "HTML",
    ".htm": "HTML",

    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "SCSS",

    ".php": "PHP",

    ".go": "Go",

    ".rs": "Rust",

    ".sol": "Solidity",

    ".kt": "Kotlin",
    ".kts": "Kotlin",

    ".swift": "Swift",

    ".sql": "SQL",

    ".vue": "Vue",

    ".dart": "Dart",
}


def language_from_filename(filename):
    lower = filename.lower()

    # Special Ruby files without normal extension
    if lower.endswith("gemfile"):
        return "Ruby"

    if lower.endswith("rakefile"):
        return "Ruby"

    for extension, language in EXTENSION_LANGUAGE.items():
        if lower.endswith(extension):
            return language

    return None


def get_commits(repo):
    owner, name = repo.split("/", 1)

    since = (
        datetime.now(timezone.utc)
        - timedelta(days=COMMIT_DAYS)
    ).isoformat()

    commits = []
    page = 1

    while True:
        params = urllib.parse.urlencode(
            {
                "author": USERNAME,
                "since": since,
                "per_page": 100,
                "page": page,
            }
        )

        try:
            data = github_request(
                f"/repos/{owner}/{name}/commits?{params}"
            )
        except Exception as e:
            print(f"Could not read commits for {repo}: {e}")
            break

        if not data:
            break

        commits.extend(data)

        if len(data) < 100:
            break

        page += 1

    return commits


def aggregate_commit_languages(repos):
    totals = defaultdict(int)

    for repo in repos:
        print(f"Reading commits: {repo}")

        commits = get_commits(repo)

        print(f"  Found {len(commits)} commits")

        owner, name = repo.split("/", 1)

        for commit in commits:
            sha = commit["sha"]

            try:
                details = github_request(
                    f"/repos/{owner}/{name}/commits/{sha}"
                )
            except Exception as e:
                print(f"Could not read {sha}: {e}")
                continue

            for file in details.get("files", []):
                language = language_from_filename(
                    file["filename"]
                )

                if not language:
                    continue

                if language in HIDDEN_LANGUAGES:
                    continue

                # Folosim numărul de modificări făcute în fișier.
                # Astfel un commit Ruby mare are mai multă greutate
                # decât o modificare de o singură linie.
                changes = file.get("changes", 1)

                totals[language] += max(changes, 1)

    return totals


COLORS = {
    "Ruby": "#CC342D",
    "JavaScript": "#F1E05A",
    "TypeScript": "#3178C6",
    "Java": "#B07219",
    "Python": "#3572A5",
    "C#": "#178600",
    "C++": "#F34B7D",
    "HTML": "#E34C26",
    "CSS": "#563D7C",
    "SCSS": "#C6538C",
    "Go": "#00ADD8",
    "Rust": "#DEA584",
    "PHP": "#4F5D95",
    "Solidity": "#AA6746",
    "Kotlin": "#A97BFF",
    "Swift": "#F05138",
    "Vue": "#41B883",
    "Dart": "#00B4AB",
    "SQL": "#E38C00",
}


FALLBACK_COLORS = [
    "#58A6FF",
    "#A371F7",
    "#3FB950",
    "#F2CC60",
    "#FF7B72",
    "#79C0FF",
    "#D2A8FF",
]


def prepare_languages(data):
    items = sorted(
        data.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    return items[:MAX_LANGUAGES]


def generate_svg(title, data, output):
    items = prepare_languages(data)

    width = 430
    height = 240

    background = "#0D1117"
    text = "#C9D1D9"
    title_color = "#FF3B8D"

    total = sum(value for _, value in items)

    if total == 0:
        total = 1

    radius = 48
    circumference = 2 * 3.141592653589793 * radius

    cx = 305
    cy = 132

    svg = []

    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
    )

    svg.append(
        f'<rect width="100%" height="100%" rx="7" '
        f'fill="{background}"/>'
    )

    svg.append(
        f'<text x="28" y="38" '
        f'font-family="Arial, sans-serif" '
        f'font-size="22" '
        f'fill="{title_color}">{title}</text>'
    )

    offset = 0

    for index, (language, value) in enumerate(items):
        percentage = value / total
        dash = percentage * circumference

        color = COLORS.get(
            language,
            FALLBACK_COLORS[
                index % len(FALLBACK_COLORS)
            ],
        )

        svg.append(
            f'<circle '
            f'cx="{cx}" cy="{cy}" r="{radius}" '
            f'fill="none" '
            f'stroke="{color}" '
            f'stroke-width="22" '
            f'stroke-dasharray="{dash} {circumference - dash}" '
            f'stroke-dashoffset="{-offset}" '
            f'transform="rotate(-90 {cx} {cy})"/>'
        )

        offset += dash

    # Hole / center
    svg.append(
        f'<circle cx="{cx}" cy="{cy}" r="36" '
        f'fill="{background}"/>'
    )

    # Legend
    legend_x = 32
    legend_y = 72

    for index, (language, value) in enumerate(items):
        percentage = value / total * 100

        color = COLORS.get(
            language,
            FALLBACK_COLORS[
                index % len(FALLBACK_COLORS)
            ],
        )

        y = legend_y + index * 23

        svg.append(
            f'<rect x="{legend_x}" y="{y - 10}" '
            f'width="13" height="13" '
            f'fill="{color}"/>'
        )

        svg.append(
            f'<text x="{legend_x + 20}" y="{y}" '
            f'font-family="Arial, sans-serif" '
            f'font-size="13" '
            f'fill="{text}">'
            f'{language} {percentage:.1f}%'
            f'</text>'
        )

    svg.append("</svg>")

    os.makedirs(
        os.path.dirname(output),
        exist_ok=True,
    )

    with open(output, "w", encoding="utf-8") as file:
        file.write("\n".join(svg))


def main():
    repos = get_user_repositories()

    print("\nRepositories:")
    for repo in repos:
        print(" -", repo)

    print("\nGenerating repository language statistics...")

    repo_languages = aggregate_repo_languages(repos)

    print(repo_languages)

    generate_svg(
        "Top Languages by Repo",
        repo_languages,
        "profile/languages-by-repo.svg",
    )

    print("\nGenerating commit language statistics...")

    commit_languages = aggregate_commit_languages(repos)

    print(commit_languages)

    generate_svg(
        "Top Languages by Commit",
        commit_languages,
        "profile/languages-by-commit.svg",
    )

    print("\nDone.")


if __name__ == "__main__":
    main()
