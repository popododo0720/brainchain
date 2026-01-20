# Plan: Session Naming + Claude Code UI 통합

## 목표
1. 세션 이름 지정 가능 (수동/자동)
2. 자동 이름: 첫 대화 요약 → 한 문장
3. Claude Code와 충돌 없이 UI 표시 (상단 바 or 사이드바)

---

## Part A: 세션 네이밍

### Task 1: 세션 모델 확장
**파일**: `brainchain/session/models.py` (수정)

```python
@dataclass
class Session:
    id: str
    name: str | None = None          # NEW: 사용자 지정 이름
    auto_name: str | None = None     # NEW: 자동 생성 이름
    created_at: datetime
    status: SessionStatus
    # ... 기존 필드

    @property
    def display_name(self) -> str:
        """표시용 이름 (우선순위: name > auto_name > id[:8])"""
        return self.name or self.auto_name or self.id[:8]
```

**acceptance_criteria**:
- [ ] name 필드 추가 (nullable)
- [ ] auto_name 필드 추가
- [ ] display_name 프로퍼티

---

### Task 2: DB 스키마 마이그레이션
**파일**: `brainchain/session/database.py` (수정)

```python
SCHEMA_VERSION = 2  # 1 → 2

MIGRATION_V2 = """
ALTER TABLE sessions ADD COLUMN name TEXT;
ALTER TABLE sessions ADD COLUMN auto_name TEXT;
"""

def migrate(self):
    if self.get_version() < 2:
        self.execute(MIGRATION_V2)
        self.set_version(2)
```

**acceptance_criteria**:
- [ ] 스키마 버전 2
- [ ] name, auto_name 컬럼 추가
- [ ] 기존 DB 마이그레이션

---

### Task 3: 자동 이름 생성
**파일**: `brainchain/session/naming.py` (NEW)

```python
class SessionNamer:
    """첫 대화에서 세션 이름 자동 생성"""

    def generate_name(self, initial_prompt: str) -> str:
        """
        프롬프트 → 한 문장 요약

        예시:
        - "Create user authentication system" → "User Auth System"
        - "Fix bug in payment processing" → "Payment Bug Fix"
        - "Add dark mode to settings" → "Dark Mode Feature"
        """
        # 방법 1: 간단한 규칙 기반
        # 방법 2: AI 호출해서 요약 (선택적)
        pass

    def slugify(self, name: str, max_len: int = 30) -> str:
        """이름을 짧게 정리"""
        pass
```

**acceptance_criteria**:
- [ ] 프롬프트에서 핵심 추출
- [ ] 30자 이내로 축약
- [ ] 특수문자 제거

---

### Task 4: CLI 옵션 추가
**파일**: `brainchain/cli.py` (수정)

```python
# 새 옵션
parser.add_argument("--name", "-n", type=str,
                    help="Session name")
parser.add_argument("--rename", nargs=2, metavar=("SESSION_ID", "NAME"),
                    help="Rename a session")

# 사용법
# brainchain --workflow "Create auth" --name "Auth Feature"
# brainchain --rename abc123 "My Auth Project"
# brainchain --sessions  # 이름으로 표시
```

**acceptance_criteria**:
- [ ] `--name` 옵션으로 세션 생성 시 이름 지정
- [ ] `--rename` 으로 기존 세션 이름 변경
- [ ] `--sessions` 목록에 이름 표시

---

## Part B: Claude Code UI 통합

### Task 5: 상단 바 컴포넌트
**파일**: `brainchain/claude_code/top_bar.py` (NEW)

```python
"""
Claude Code 출력 최상단에 brainchain 상태 표시
(Claude 기본 UI 위에 덧붙임)

┌─ 🧠 Brainchain ──────────────────────────────────────┐
│ Session: Auth Feature │ Tasks: 3/5 │ Context: 62%   │
└──────────────────────────────────────────────────────┘

... Claude Code 기본 출력 ...
"""

class TopBar:
    def render(self, session: Session) -> str:
        return f"""
┌─ 🧠 Brainchain ──────────────────────────────────────┐
│ Session: {session.display_name:<20} │ {self.status()} │
└──────────────────────────────────────────────────────┘
"""

    def inject_to_output(self, claude_output: str) -> str:
        """Claude 출력 앞에 상단바 추가"""
        return self.render() + "\n" + claude_output
```

**acceptance_criteria**:
- [ ] 세션 이름 표시
- [ ] 진행 상태 표시
- [ ] Claude 출력과 구분되는 스타일

---

### Task 6: 사이드바 (TUI 모드)
**파일**: `brainchain/tui/widgets/sidebar.py` (NEW)

```python
"""
TUI 모드에서 왼쪽 사이드바로 세션 목록 표시

┌──────────┬─────────────────────────────────────────┐
│ Sessions │                                         │
│──────────│          Main Content                   │
│ ● Auth   │                                         │
│   Feature│                                         │
│ ○ Bug Fix│                                         │
│ ○ Refact │                                         │
│          │                                         │
│ [+] New  │                                         │
└──────────┴─────────────────────────────────────────┘
"""

class SessionSidebar(Container):
    def compose(self):
        yield Static("Sessions", classes="sidebar-title")
        yield ListView(id="session-list")
        yield Button("[+] New", id="new-session")

    def on_list_view_selected(self, event):
        """세션 선택 시 전환"""
        self.switch_session(event.item.session_id)
```

**acceptance_criteria**:
- [ ] 세션 목록 표시 (이름으로)
- [ ] 현재 세션 하이라이트
- [ ] 클릭으로 세션 전환
- [ ] 새 세션 생성 버튼

---

### Task 7: Claude Code 훅 시스템
**파일**: `brainchain/claude_code/hooks.py` (NEW)

```python
"""
Claude Code 출력을 가로채서 brainchain UI 추가

훅 포인트:
1. before_output: 출력 전 상단바 추가
2. after_command: 명령 실행 후 상태 업데이트
3. on_context_change: 컨텍스트 변경 시 알림
"""

class ClaudeCodeHooks:
    def __init__(self, mode: str = "top_bar"):
        self.mode = mode  # "top_bar" | "sidebar" | "minimal"

    def wrap_output(self, output: str, session: Session) -> str:
        if self.mode == "top_bar":
            return TopBar().inject(output, session)
        elif self.mode == "minimal":
            return f"[{session.display_name}] " + output
        return output

    def register(self):
        """Claude Code에 훅 등록"""
        # MCP 또는 환경변수로 연동
        pass
```

**acceptance_criteria**:
- [ ] 출력 래핑 시스템
- [ ] 모드 선택 (top_bar/sidebar/minimal)
- [ ] Claude Code와 안전하게 연동

---

### Task 8: 설정 통합
**파일**: `config.toml` 추가

```toml
[session]
auto_name = true              # 자동 이름 생성
name_max_length = 30          # 이름 최대 길이

[claude_code]
ui_mode = "top_bar"           # "top_bar" | "sidebar" | "minimal" | "none"
show_progress = true          # 진행률 표시
show_context = true           # 컨텍스트 사용률 표시
```

**파일**: `brainchain/config.py` (수정)

**acceptance_criteria**:
- [ ] session 섹션 추가
- [ ] claude_code 섹션 추가
- [ ] 기본값 설정

---

## 파일 구조
```
brainchain/
├── session/
│   ├── models.py          # Task 1 (수정)
│   ├── database.py        # Task 2 (수정)
│   └── naming.py          # Task 3 (NEW)
├── claude_code/           # NEW 폴더
│   ├── __init__.py
│   ├── top_bar.py         # Task 5
│   └── hooks.py           # Task 7
├── tui/
│   └── widgets/
│       └── sidebar.py     # Task 6
├── cli.py                 # Task 4 (수정)
└── config.py              # Task 8 (수정)
```

---

## 병렬 실행

```
Round 1: Task 1 + Task 3 + Task 5 + Task 6  (4개 병렬!)
         - models.py, naming.py, top_bar.py, sidebar.py
         - 파일 안 겹침

Round 2: Task 2 + Task 7 + Task 8           (3개 병렬)
         - database.py, hooks.py, config.py
         - 파일 안 겹침

Round 3: Task 4                              (순차)
         - cli.py (다른 것들 의존)
```

---

## UI 미리보기

### 모드 1: Top Bar (기본)
```
┌─ 🧠 Brainchain ──────────────────────────────────────┐
│ 📁 Auth Feature │ ████████░░ 4/5 │ 🧠 62% │ ⏱ 3:42  │
└──────────────────────────────────────────────────────┘

╭─ Claude Code ────────────────────────────────────────╮
│ I'll help you implement the authentication system...│
╰──────────────────────────────────────────────────────╯
```

### 모드 2: Sidebar (TUI)
```
┌────────────┬────────────────────────────────────────┐
│  Sessions  │                                        │
│────────────│  Claude Code Output                    │
│ ● Auth     │                                        │
│   Feature  │  I'll implement the user model...     │
│ ○ Payment  │                                        │
│   Bug      │  ```python                            │
│ ○ Dark     │  class User:                          │
│   Mode     │      ...                              │
│            │  ```                                  │
│ [+] New    │                                        │
└────────────┴────────────────────────────────────────┘
```

### 모드 3: Minimal
```
[Auth Feature] I'll help you implement...
```

---

## Part C: 키보드 단축키 (OpenCode 스타일)

### Task 9: 단축키 핸들러
**파일**: `brainchain/tui/keybindings.py` (NEW)

```python
"""
전역 키보드 단축키

Ctrl+T  → 세션 팔레트 (이전 세션 목록)
Ctrl+N  → 새 세션
Ctrl+B  → 사이드바 토글
Ctrl+P  → 명령 팔레트
Ctrl+L  → 로그 토글
Escape  → 팔레트 닫기
"""

from textual.binding import Binding

KEYBINDINGS = [
    Binding("ctrl+t", "show_session_palette", "Sessions", show=True),
    Binding("ctrl+n", "new_session", "New Session", show=True),
    Binding("ctrl+b", "toggle_sidebar", "Sidebar", show=True),
    Binding("ctrl+p", "show_command_palette", "Commands", show=False),
    Binding("ctrl+l", "toggle_logs", "Logs", show=False),
    Binding("escape", "close_palette", "Close", show=False),
]

class KeybindingsMixin:
    """앱에 믹스인으로 추가"""

    def action_show_session_palette(self):
        self.push_screen(SessionPalette())

    def action_new_session(self):
        self.create_new_session()

    def action_toggle_sidebar(self):
        sidebar = self.query_one("#sidebar")
        sidebar.toggle_class("hidden")
```

**acceptance_criteria**:
- [ ] Ctrl+T 세션 팔레트
- [ ] Ctrl+N 새 세션
- [ ] Ctrl+B 사이드바 토글
- [ ] ESC 닫기

---

### Task 10: 세션 팔레트 (Ctrl+T)
**파일**: `brainchain/tui/widgets/session_palette.py` (NEW)

```python
"""
Ctrl+T 누르면 나오는 세션 선택 팔레트

┌─────────────────────────────────────────────┐
│ 🔍 Search sessions...                       │
├─────────────────────────────────────────────┤
│ ● Auth Feature          today 14:30    4/5 │
│   Payment Bug Fix       today 10:15    3/3 │
│   Dark Mode             yesterday      5/5 │
│   API Refactoring       2 days ago     2/8 │
├─────────────────────────────────────────────┤
│ [Enter] Switch  [Ctrl+N] New  [Esc] Close  │
└─────────────────────────────────────────────┘
"""

class SessionPalette(ModalScreen):
    BINDINGS = [
        ("escape", "close", "Close"),
        ("enter", "select", "Select"),
        ("ctrl+n", "new", "New Session"),
    ]

    def compose(self):
        yield Input(placeholder="Search sessions...", id="search")
        yield ListView(id="session-list")
        yield Static("[Enter] Switch  [Ctrl+N] New  [Esc] Close")

    def on_input_changed(self, event):
        """검색 필터링"""
        self.filter_sessions(event.value)

    def action_select(self):
        """선택한 세션으로 전환"""
        selected = self.query_one("#session-list").highlighted
        self.app.switch_session(selected.session_id)
        self.dismiss()
```

**acceptance_criteria**:
- [ ] 모달 팔레트 UI
- [ ] 실시간 검색/필터
- [ ] 키보드로 탐색 (↑↓)
- [ ] Enter로 선택, Esc로 닫기

---

### Task 11: 명령 팔레트 (Ctrl+P)
**파일**: `brainchain/tui/widgets/command_palette.py` (NEW)

```python
"""
Ctrl+P 누르면 나오는 명령 팔레트

┌─────────────────────────────────────────────┐
│ > _                                         │
├─────────────────────────────────────────────┤
│ 📁 New Session              Ctrl+N          │
│ 🔄 Resume Session           Ctrl+T          │
│ 📊 Toggle Sidebar           Ctrl+B          │
│ 🎨 Change Theme                             │
│ ⚙️  Settings                                │
│ 🗑️  Delete Session                          │
│ 📤 Export Session                           │
└─────────────────────────────────────────────┘
"""

COMMANDS = [
    Command("new_session", "New Session", "ctrl+n", icon="📁"),
    Command("resume_session", "Resume Session", "ctrl+t", icon="🔄"),
    Command("toggle_sidebar", "Toggle Sidebar", "ctrl+b", icon="📊"),
    Command("change_theme", "Change Theme", None, icon="🎨"),
    Command("settings", "Settings", None, icon="⚙️"),
    Command("delete_session", "Delete Session", None, icon="🗑️"),
    Command("export_session", "Export Session", None, icon="📤"),
]

class CommandPalette(ModalScreen):
    def compose(self):
        yield Input(placeholder=">", id="command-input")
        yield ListView(id="command-list")

    def on_input_changed(self, event):
        self.filter_commands(event.value)
```

**acceptance_criteria**:
- [ ] 명령 목록 표시
- [ ] fuzzy 검색
- [ ] 단축키 힌트 표시
- [ ] 실행 후 자동 닫힘

---

### Task 12: app.py 통합
**파일**: `brainchain/tui/app.py` (수정)

```python
from .keybindings import KEYBINDINGS, KeybindingsMixin

class BrainchainApp(App, KeybindingsMixin):
    BINDINGS = KEYBINDINGS + [
        # 기존 바인딩
        ("f1", "show_tab('plan')", "Plan"),
        ("f2", "show_tab('tasks')", "Tasks"),
        # ...
    ]

    def compose(self):
        yield Header()
        yield Horizontal(
            SessionSidebar(id="sidebar"),  # 사이드바
            TabbedContent(...)              # 메인 컨텐츠
        )
        yield Footer()
```

**acceptance_criteria**:
- [ ] 키바인딩 믹스인 적용
- [ ] 사이드바 레이아웃
- [ ] 팔레트 연동

---

## 업데이트된 파일 구조
```
brainchain/
├── tui/
│   ├── app.py              # Task 12 (수정)
│   ├── keybindings.py      # Task 9 (NEW)
│   └── widgets/
│       ├── sidebar.py       # Task 6
│       ├── session_palette.py  # Task 10 (NEW)
│       └── command_palette.py  # Task 11 (NEW)
```

---

## 업데이트된 병렬 실행

```
Round 1: Task 1 + Task 3 + Task 5 + Task 6   (4개)
Round 2: Task 2 + Task 7 + Task 8            (3개)
Round 3: Task 9 + Task 10 + Task 11          (3개 - NEW!)
Round 4: Task 4 + Task 12                    (2개)
```

---

## 단축키 요약

| 단축키 | 동작 |
|--------|------|
| `Ctrl+T` | 세션 팔레트 (이전 세션 목록) |
| `Ctrl+N` | 새 세션 생성 |
| `Ctrl+B` | 사이드바 토글 |
| `Ctrl+P` | 명령 팔레트 |
| `Ctrl+L` | 로그 토글 |
| `F1-F4` | 탭 전환 |
| `↑↓` | 목록 탐색 |
| `Enter` | 선택 |
| `Escape` | 닫기 |
