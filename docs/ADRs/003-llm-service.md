# ADR-003. LLM Service

Date: 2026-01-25
Status: Proposed

## Context
The primary use for this server is to provide access to LLMs for our research community. There are some well-established inference engines for LLMs, including vLLM, ollama, llama.cpp, and sglang. This discussion involves weighing up the difference inference engines.

There is also a connection between inference engine, use cases, and how we optimize and benchmark the service.

### Different engines for different uses
It seems we can split inference engines into two categories based on scale:
**
**single users with hardware constraints**
- ollama
- llama cpp

**multi user, scalable**
- sglang
- vllm

The distinction between SGLang and vLLM seems to come down to whether or not you want multi-turn conversational abilities. With something like ChatGPT, the context builds over time. Processing this context every time the user submits a new query is a waste of time. But SGLang and vLLM have different solutions.

vLLM caches exact prefix matches using block-level storage, which therefore requires identical token sequences to trigger cache hits. It is optimized for batch inference, and manual configuration is needed in order to optimize cache utilization. SGLang uses a tree structure for sequence matching, and allows partial matches.

Since we already have experience with vLLM, and we know other people at the University also use vLLM, we are leaning toward vLLM.

## Decision
- The team has experience with vLLM  
- Low effort to set up  
- OpenAI API compatible  

## Consequences
Our service will not be optimized for turn-based conversations and agentic applications at this stage.

Work is required to examine differences in performance for different tasks. It seems easy enough to swap out SGLang and vLLM.