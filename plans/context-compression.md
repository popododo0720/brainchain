# Plan: Context Compression (oh-my-opencode 스타일)

## 목표
세션 컨텍스트가 커지면 자동으로 압축하여 토큰 한도 내에서 작업 지속

## 트리거 임계값
```
70% → 리마인더 ("여유 있음, 급하게 굴지 마")
85% → Pre-compression (오래된 메시지 요약)
95% → Auto-compact (전체 세션 요약 + 리셋)
```

---

## Task 1: 토큰 카운터
**파일**: `brainchain/context/counter.py`

```python
class TokenCounter:
    """모델별 토큰 한도 및 현재 사용량 추적"""

    MODEL_LIMITS = {
        "claude-opus": 200_000,
        "claude-sonnet": 200_000,
        "gpt-5.2": 128_000,
    }

    def count(self, text: str) -> int:
        """간단한 추정: 4자 = 1토큰"""
        return len(text) // 4

    def usage_percent(self, session: Session) -> float:
        """현재 세션의 컨텍스트 사용률"""
        pass
```

**acceptance_criteria**:
- [ ] 모델별 한도 정의
- [ ] 세션 메시지 합산 토큰 계산
- [ ] 사용률 퍼센트 반환

---

## Task 2: 컨텍스트 모니터
**파일**: `brainchain/context/monitor.py`

```python
class ContextMonitor:
    """사용률 감시 + 훅 트리거"""

    THRESHOLDS = {
        "remind": 0.70,
        "compress": 0.85,
        "compact": 0.95,
    }

    def check(self, session: Session) -> Action | None:
        """임계값 체크 → 액션 반환"""
        pass
```

**acceptance_criteria**:
- [ ] 70% → `Action.REMIND`
- [ ] 85% → `Action.COMPRESS`
- [ ] 95% → `Action.COMPACT`

---

## Task 3: 압축 엔진
**파일**: `brainchain/context/compressor.py`

```python
class Compressor:
    """메시지 압축/요약"""

    def summarize_messages(self, messages: list[Message]) -> Message:
        """여러 메시지 → 1개 요약 메시지"""
        # 외부 CLI 호출해서 요약 생성
        pass

    def prune_tool_outputs(self, messages: list[Message]) -> list[Message]:
        """도구 출력 중 오래된 것 제거"""
        pass

    def compact_session(self, session: Session) -> Session:
        """전체 세션 요약 후 새 세션 시작"""
        pass
```

**acceptance_criteria**:
- [ ] 오래된 메시지 N개 → 요약 1개로 교체
- [ ] 도구 출력 pruning (결과만 남기고 상세 제거)
- [ ] 전체 compact 시 이전 세션 링크 유지

---

## Task 4: 훅 시스템 통합
**파일**: `brainchain/context/hooks.py`

```python
# config.toml 설정
# [context]
# auto_compress = true
# thresholds = { remind = 0.70, compress = 0.85, compact = 0.95 }

class ContextHooks:
    """워크플로우 실행 전후 컨텍스트 체크"""

    def before_step(self, session: Session):
        """스텝 실행 전 체크"""
        action = self.monitor.check(session)
        if action == Action.COMPRESS:
            self.compressor.summarize_old_messages(session)

    def after_step(self, session: Session):
        """스텝 실행 후 정리"""
        pass
```

**acceptance_criteria**:
- [ ] workflow.py에 훅 호출 추가
- [ ] config.toml에 설정 옵션
- [ ] 비활성화 가능 (`auto_compress = false`)

---

## Task 5: UI 피드백
**파일**: `brainchain/ui.py` (수정)

```python
def show_context_status(usage_percent: float):
    """컨텍스트 사용률 표시"""
    # [████████░░] 80% context used
    pass

def show_compression_notice(action: Action):
    """압축 발생 시 알림"""
    # ⚡ Compressing old messages...
    pass
```

**acceptance_criteria**:
- [ ] 프로그레스 바 형태로 사용률 표시
- [ ] 압축 시 사용자에게 알림

---

## 파일 구조
```
brainchain/
├── context/           # NEW
│   ├── __init__.py
│   ├── counter.py     # Task 1
│   ├── monitor.py     # Task 2
│   ├── compressor.py  # Task 3
│   └── hooks.py       # Task 4
├── ui.py              # Task 5 (수정)
└── workflow.py        # Task 4 (수정)
```

## 의존성
```
Task 1 ← Task 2 ← Task 3 ← Task 4
                          ↑
                      Task 5
```

## 병렬 실행 가능
- **Round 1**: Task 1, Task 5 (독립)
- **Round 2**: Task 2
- **Round 3**: Task 3
- **Round 4**: Task 4 (통합)

---

## 예상 config.toml 추가
```toml
[context]
auto_compress = true
remind_threshold = 0.70
compress_threshold = 0.85
compact_threshold = 0.95
keep_recent_messages = 10  # 최근 N개는 압축 안 함
```
