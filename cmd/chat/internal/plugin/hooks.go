package plugin

import (
	"sort"
	"sync"
)

type HookType string

const (
	HookPreExecute       HookType = "pre_execute"
	HookPostExecute      HookType = "post_execute"
	HookOnError          HookType = "on_error"
	HookOnInput          HookType = "on_input"
	HookOnOutput         HookType = "on_output"
	HookOnSessionStart   HookType = "on_session_start"
	HookOnSessionEnd     HookType = "on_session_end"
	HookOnStepStart      HookType = "on_step_start"
	HookOnStepEnd        HookType = "on_step_end"
	HookOnContextWarning HookType = "on_context_warning"
	HookOnContextCompress HookType = "on_context_compress"
)

type HookContext struct {
	HookType HookType
	Data     map[string]any

	Role   string
	Agent  string
	Prompt string

	Result    any
	Error     error
	SessionID string
	Cwd       string

	ModifiedPrompt string
	ModifiedOutput string
	ShouldSkip     bool
	ShouldRetry    bool
}

type HookHandler func(*HookContext) *HookContext

type Hook struct {
	Type     HookType
	Handler  HookHandler
	Priority int
	Name     string
	Plugin   string
	Enabled  bool
}

type HookRegistry struct {
	hooks map[HookType][]*Hook
	mu    sync.RWMutex
}

func NewHookRegistry() *HookRegistry {
	r := &HookRegistry{
		hooks: make(map[HookType][]*Hook),
	}
	for _, t := range []HookType{
		HookPreExecute, HookPostExecute, HookOnError,
		HookOnInput, HookOnOutput,
		HookOnSessionStart, HookOnSessionEnd,
		HookOnStepStart, HookOnStepEnd,
		HookOnContextWarning, HookOnContextCompress,
	} {
		r.hooks[t] = []*Hook{}
	}
	return r
}

func (r *HookRegistry) Register(hookType HookType, handler HookHandler, priority int, name, plugin string) *Hook {
	r.mu.Lock()
	defer r.mu.Unlock()

	hook := &Hook{
		Type:     hookType,
		Handler:  handler,
		Priority: priority,
		Name:     name,
		Plugin:   plugin,
		Enabled:  true,
	}

	r.hooks[hookType] = append(r.hooks[hookType], hook)
	sort.Slice(r.hooks[hookType], func(i, j int) bool {
		return r.hooks[hookType][i].Priority < r.hooks[hookType][j].Priority
	})

	return hook
}

func (r *HookRegistry) Unregister(hook *Hook) bool {
	r.mu.Lock()
	defer r.mu.Unlock()

	hooks := r.hooks[hook.Type]
	for i, h := range hooks {
		if h == hook {
			r.hooks[hook.Type] = append(hooks[:i], hooks[i+1:]...)
			return true
		}
	}
	return false
}

func (r *HookRegistry) UnregisterByPlugin(plugin string) int {
	r.mu.Lock()
	defer r.mu.Unlock()

	removed := 0
	for t := range r.hooks {
		var kept []*Hook
		for _, h := range r.hooks[t] {
			if h.Plugin != plugin {
				kept = append(kept, h)
			} else {
				removed++
			}
		}
		r.hooks[t] = kept
	}
	return removed
}

func (r *HookRegistry) Trigger(hookType HookType, ctx *HookContext) *HookContext {
	r.mu.RLock()
	hooks := make([]*Hook, len(r.hooks[hookType]))
	copy(hooks, r.hooks[hookType])
	r.mu.RUnlock()

	if ctx == nil {
		ctx = &HookContext{HookType: hookType, Data: make(map[string]any)}
	}
	if ctx.Data == nil {
		ctx.Data = make(map[string]any)
	}

	for _, hook := range hooks {
		if !hook.Enabled {
			continue
		}

		result := hook.Handler(ctx)
		if result != nil {
			ctx = result
		}

		if ctx.ShouldSkip {
			break
		}
	}

	return ctx
}

func (r *HookRegistry) GetHooks(hookType HookType) []*Hook {
	r.mu.RLock()
	defer r.mu.RUnlock()

	result := make([]*Hook, len(r.hooks[hookType]))
	copy(result, r.hooks[hookType])
	return result
}

func (r *HookRegistry) PreExecute(role, agent, prompt string) *HookContext {
	return r.Trigger(HookPreExecute, &HookContext{
		HookType: HookPreExecute,
		Role:     role,
		Agent:    agent,
		Prompt:   prompt,
	})
}

func (r *HookRegistry) PostExecute(role, agent string, result any) *HookContext {
	return r.Trigger(HookPostExecute, &HookContext{
		HookType: HookPostExecute,
		Role:     role,
		Agent:    agent,
		Result:   result,
	})
}

func (r *HookRegistry) OnError(err error, role string) *HookContext {
	return r.Trigger(HookOnError, &HookContext{
		HookType: HookOnError,
		Error:    err,
		Role:     role,
	})
}

func (r *HookRegistry) ProcessInput(input string) string {
	ctx := r.Trigger(HookOnInput, &HookContext{
		HookType: HookOnInput,
		Prompt:   input,
	})
	if ctx.ModifiedPrompt != "" {
		return ctx.ModifiedPrompt
	}
	return input
}

func (r *HookRegistry) ProcessOutput(output string) string {
	ctx := r.Trigger(HookOnOutput, &HookContext{
		HookType:       HookOnOutput,
		ModifiedOutput: output,
	})
	if ctx.ModifiedOutput != "" {
		return ctx.ModifiedOutput
	}
	return output
}
