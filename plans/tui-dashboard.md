# Plan: TUI Dashboard (터미널 대시보드)

## 목표
탭 기반 인터랙티브 TUI로 워크플로우 진행상황, 역할별 뷰, 세션 관리 제공

## 라이브러리 선택
```
textual (권장) - 모던 TUI, async 지원, 위젯 풍부
  or
rich + prompt_toolkit - 가벼움, 이미 일부 사용중
```

---

## 화면 구성

```
┌─ Brainchain v0.2.0 ─────────────────────────────────────────┐
│  [F1:Plan] [F2:Tasks] [F3:Logs] [F4:Sessions] [F5:Config]  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   현재 탭 내용                                               │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ Status: Running planner │ Context: 45% │ Time: 00:02:34    │
└─────────────────────────────────────────────────────────────┘
```

---

## Task 1: TUI 프레임워크 설정
**파일**: `brainchain/tui/__init__.py`, `brainchain/tui/app.py`

```python
from textual.app import App
from textual.widgets import Header, Footer, TabbedContent, TabPane

class BrainchainApp(App):
    BINDINGS = [
        ("f1", "show_tab('plan')", "Plan"),
        ("f2", "show_tab('tasks')", "Tasks"),
        ("f3", "show_tab('logs')", "Logs"),
        ("f4", "show_tab('sessions')", "Sessions"),
        ("q", "quit", "Quit"),
    ]

    def compose(self):
        yield Header()
        with TabbedContent():
            yield TabPane("Plan", id="plan")
            yield TabPane("Tasks", id="tasks")
            yield TabPane("Logs", id="logs")
            yield TabPane("Sessions", id="sessions")
        yield Footer()
```

**acceptance_criteria**:
- [ ] textual 앱 기본 구조
- [ ] F1-F4 탭 전환
- [ ] 헤더/푸터 표시

---

## Task 2: Plan 탭 (플래너 뷰)
**파일**: `brainchain/tui/views/plan.py`

```python
class PlanView(Container):
    """현재 계획 표시 + 편집"""

    def compose(self):
        yield Static("## Current Plan", classes="title")
        yield PlanTree(self.plan)  # 트리 형태로 태스크 표시
        yield Button("Re-plan", id="replan")

class PlanTree(Tree):
    """계획을 트리로 시각화"""
    # specs/
    #   ├── api.md
    #   └── db.md
    # tasks/
    #   ├── [x] Task 1: User model
    #   ├── [→] Task 2: Auth routes (running)
    #   └── [ ] Task 3: Tests
```

**acceptance_criteria**:
- [ ] 현재 plan.json 파싱 및 표시
- [ ] 완료/진행중/대기 상태 표시
- [ ] 태스크 선택 시 상세 정보

---

## Task 3: Tasks 탭 (진행상황)
**파일**: `brainchain/tui/views/tasks.py`

```python
class TasksView(Container):
    """실시간 태스크 진행상황"""

    def compose(self):
        yield DataTable(id="task-table")
        yield ProgressBar(id="overall-progress")
        yield Log(id="current-output")  # 현재 실행중인 태스크 출력

class TaskRow:
    """
    │ ID │ Role        │ Status  │ Progress │ Duration │
    │ 1  │ implementer │ running │ ████░░   │ 00:01:23 │
    │ 2  │ implementer │ pending │ ░░░░░░   │ --:--:-- │
    """
```

**acceptance_criteria**:
- [ ] 테이블 형태 태스크 목록
- [ ] 실시간 진행률 업데이트
- [ ] 현재 태스크 출력 스트리밍

---

## Task 4: Logs 탭 (실시간 로그)
**파일**: `brainchain/tui/views/logs.py`

```python
class LogsView(Container):
    """모든 에이전트 출력 통합 로그"""

    def compose(self):
        yield RichLog(id="log-view", highlight=True, markup=True)
        yield Input(placeholder="Filter logs...", id="log-filter")

    def on_log_message(self, message: LogMessage):
        """새 로그 추가"""
        self.query_one("#log-view").write(message)
```

**acceptance_criteria**:
- [ ] 역할별 색상 구분
- [ ] 실시간 스트리밍
- [ ] 필터링 (role, level)

---

## Task 5: Sessions 탭
**파일**: `brainchain/tui/views/sessions.py`

```python
class SessionsView(Container):
    """세션 목록 + 재개/삭제"""

    def compose(self):
        yield DataTable(id="session-table")
        yield Button("Resume", id="resume")
        yield Button("Delete", id="delete")

    # │ ID     │ Status    │ Workflow │ Created    │ Tasks │
    # │ abc123 │ completed │ default  │ 2025-01-20 │ 5/5   │
    # │ def456 │ failed    │ default  │ 2025-01-19 │ 3/5   │
```

**acceptance_criteria**:
- [ ] SQLite에서 세션 목록 로드
- [ ] 선택 후 Resume/Delete
- [ ] 세션 상세 정보 표시

---

## Task 6: 상태바 (하단)
**파일**: `brainchain/tui/widgets/statusbar.py`

```python
class StatusBar(Static):
    """하단 상태 표시줄"""

    def compose(self):
        yield Static(id="current-role")      # "Running: planner"
        yield Static(id="context-usage")     # "Context: 45%"
        yield Static(id="elapsed-time")      # "Time: 00:02:34"
        yield Static(id="session-id")        # "Session: abc123"
```

**acceptance_criteria**:
- [ ] 현재 역할/상태
- [ ] 컨텍스트 사용률 (압축 계획과 연동)
- [ ] 경과 시간
- [ ] 세션 ID

---

## Task 7: 테마 시스템
**파일**: `brainchain/tui/themes.py`

```python
THEMES = {
    "default": {
        "primary": "#7C3AED",    # purple
        "success": "#10B981",    # green
        "warning": "#F59E0B",    # yellow
        "error": "#EF4444",      # red
        "background": "#1F2937",
        "surface": "#374151",
    },
    "ocean": { ... },
    "forest": { ... },
    "mono": { ... },
}

# config.toml
# [tui]
# theme = "default"
# show_status_bar = true
```

**acceptance_criteria**:
- [ ] 테마 정의 구조
- [ ] config.toml에서 테마 선택
- [ ] 런타임 테마 전환 (선택)

---

## Task 8: CLI 통합
**파일**: `brainchain/cli.py` (수정)

```python
# 새 옵션 추가
parser.add_argument("--tui", action="store_true", help="Launch TUI dashboard")
parser.add_argument("--theme", type=str, help="TUI theme name")

# 사용법
# brainchain --tui
# brainchain --tui --theme ocean
# brainchain --workflow "Create auth" --tui  # TUI로 워크플로우 실행
```

**acceptance_criteria**:
- [ ] `--tui` 플래그로 TUI 모드 실행
- [ ] `--theme` 옵션
- [ ] 워크플로우와 TUI 동시 실행

---

## 파일 구조
```
brainchain/
├── tui/                    # NEW
│   ├── __init__.py
│   ├── app.py              # Task 1: 메인 앱
│   ├── themes.py           # Task 7: 테마
│   ├── views/
│   │   ├── __init__.py
│   │   ├── plan.py         # Task 2
│   │   ├── tasks.py        # Task 3
│   │   ├── logs.py         # Task 4
│   │   └── sessions.py     # Task 5
│   └── widgets/
│       ├── __init__.py
│       ├── statusbar.py    # Task 6
│       └── progress.py
├── cli.py                  # Task 8 (수정)
└── pyproject.toml          # textual 의존성 추가
```

## 의존성 추가
```toml
[project.optional-dependencies]
tui = ["textual>=0.50.0", "rich>=13.0.0"]
```

---

## 병렬 실행 가능
```
Round 1: Task 1 (앱 뼈대) + Task 7 (테마)
Round 2: Task 2, 3, 4, 5 (각 탭 뷰 - 병렬!)
Round 3: Task 6 (상태바)
Round 4: Task 8 (CLI 통합)
```

---

## 예상 실행 화면

```
┌─ Brainchain v0.2.0 ─────────────────────────────────────────┐
│  [F1:Plan] [F2:Tasks] [F3:Logs] [F4:Sessions]              │
├─────────────────────────────────────────────────────────────┤
│  ## Tasks                                                   │
│  ┌────┬─────────────┬──────────┬──────────┬──────────┐     │
│  │ ID │ Role        │ Status   │ Progress │ Duration │     │
│  ├────┼─────────────┼──────────┼──────────┼──────────┤     │
│  │ 1  │ planner     │ ✓ done   │ ████████ │ 00:00:45 │     │
│  │ 2  │ validator   │ ✓ done   │ ████████ │ 00:00:12 │     │
│  │ 3  │ implementer │ → running│ ████░░░░ │ 00:01:23 │     │
│  │ 4  │ implementer │ ○ pending│ ░░░░░░░░ │ --:--:-- │     │
│  │ 5  │ reviewer    │ ○ pending│ ░░░░░░░░ │ --:--:-- │     │
│  └────┴─────────────┴──────────┴──────────┴──────────┘     │
│                                                             │
│  Current output:                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Implementing user model in src/models/user.py...    │   │
│  │ Creating User class with fields: id, email, name... │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│ ● implementer │ Context: [████░░░░] 52% │ ⏱ 00:02:20      │
└─────────────────────────────────────────────────────────────┘
 Q:Quit  F1-F4:Tabs  R:Re-run  P:Pause
```
