# Implementation Tasks

## 1. Update Agent Dependencies

- [ ] 1.1 Add `_session_manager` private field to `AgentDependencies` dataclass (src/agent/dependencies.py:70)
- [ ] 1.2 Remove `active_deck_id` from dataclass fields
- [ ] 1.3 Add `active_deck_id` as a `@property` that calls `self._session_manager.get_active_deck_id(self.session_id)`
- [ ] 1.4 Import `ConversationSessionManager` type for type hints

## 2. Update Dependency Injection

- [ ] 2.1 Modify `get_agent_dependencies()` to pass `_session_manager` reference instead of `active_deck_id` snapshot (src/ui/app.py:126-132)
- [ ] 2.2 Import `_session_manager` from `src.agent.core`

## 3. Testing

- [ ] 3.1 Test multi-tool scenario: Create deck → Add card (in same agent run)
- [ ] 3.2 Test multi-tool scenario: Load deck → Add card (in same agent run)
- [ ] 3.3 Test multi-tool scenario: View deck → Remove card (in same agent run)
- [ ] 3.4 Verify session isolation (different sessions have different active decks)
- [ ] 3.5 Verify persistence across messages (active deck survives between agent runs)

## 4. Validation

- [ ] 4.1 Run `openspec validate fix-active-deck-session-sync --strict`
- [ ] 4.2 Verify all unit tests pass (`uv run pytest tests/unit/`)
- [ ] 4.3 Verify integration tests pass (`uv run pytest tests/integration/ -m integration`)
- [ ] 4.4 Manual testing: Create and build a full deck in one conversation
