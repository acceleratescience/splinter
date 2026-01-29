# LLM Performance Metrics

## Introduction
The primary purpose of this server is to deliver free and open source LLMs to the Cambridge community. We have limited hardware, and we therefore need to extract as much performance as possible out of it, in order to serve as many users as possible.

This document represents the learnings from benchmarking our system to optimize for different use cases.

## Considerations
In order to optimize performance, we have to consider the appropiate uses of our endpoints. ADR-003 establishes the fair-use policy of our endpoints. Importantly, they are not to be used for the creation of long-term chatbots, or ChatGPT clones. The idea is that we don't want people plugging our endpoints into a streamlit frontend, and using it as an assistant.

However, this is not say that some chat-like uses are not allowed.

## Stages of inference
After the uses packages up their prompt into a request, a number of things happen sequentially:

1. **Queuing** The prompt joins a queue for processing
2. **Prefill** The prompt tokens are run through the model layers, and the KV cache is filled for these tokens. This is compute bound, and usually very fast on something like an H100. The result of this process is the first token.
3. **Decode** The LLM must now output a response, one token at a time. This process is memory bound, because to generate a single token, the GPU must read the parameters and the KV cache from the HBM into the compute cores. And it has to do this _every_ time it generates a token.

## Metrics
**Time to first token (TTFT)** is the time it takes from when the prompt is sent to when the model spits out the first token. It includes tokenization, prefill, the first token decode, detokenization, and the reception of that token. The longer the input sequence, the longer the TTFT.

**End-to-end latency (ETEL)** is the time it takes from submitting a query to receiving a full response. So all of the above, plus the full decode phase. It is given by

$$
ETEL = TTFT + decode
$$

where $decode$ is the time from when the first token is received to when the final token is received.

**Intertoken latency (ITL) or time per output token (TPOT)** is the average time between consecutive tokens. ITL is given by

$$
ITL = \frac{ETEL - TTFT}{\textrm{total output tokens} - 1}
$$

These definitions may sound simple, but there appear to be some difference between how different benchmarkers calculate these metrics. For example, are you supposed to include the stop token in this calculation?

As the output sequence grows, so does the KV cache, and the memory usage along with it. The arithmetic cost also grows linearly with the length of the input plus output sequence, but ITL is memory-bound.

**Tokens per second (TPS)** is the total output tokens per second (unsurprisingly), and accounts for all concurrent requests. As requests increase, TPS increases. This actually confused me when I started running benchmarks with more concurrent requests. It is given by

$$
TPS = \frac{\textrm{total output tokens}}{T_{end} - T_{start}}
$$

TPS is done in a batch fashion, and therefore may not be indicative of true TPS in live scenarios.

**TPS per user** is the same as above but per user.

As the number of concurrent requests increases, TPS will increase, while TPS per user will decrease as latency increases.

**Requests per second (RPS)** is the average number of requests that be completed in one second. It is given by

$$
RPS = \frac{\textrm{total completed requests}}{T_{end} - T_{start}}
$$

## Measuring these metrics
We have a choice of a few benchmarking libraries. Our constraints are simple: any benchmarking library we use has to be compatible with the OpenAI API. In other words, we should have a model in service, and we should be able to use the library to hammer it. The best choices at the moment seem to be:

- GenAI Perf from NVIDIA
- vLLM

Fortunately, we can compare both frameworks and ensure consistency.

## vLLM


## First optimizations
Perhaps the first step should be to optimize for context size.

Per request, we should log:
- Input token count
- Output token count
- Time to first token
- Total latency
- API key
- Timestamp

## References

[Mastering LLM Techniques: Inference Optimization](https://developer.nvidia.com/blog/mastering-llm-techniques-inference-optimization/)
[LLM Inference Benchmarking: Fundamental Concepts](https://developer.nvidia.com/blog/llm-benchmarking-fundamental-concepts/)
[LLM Inference Benchmarking Guide: NVIDIA GenAI-Perf and NIM](https://developer.nvidia.com/blog/llm-performance-benchmarking-measuring-nvidia-nim-performance-with-genai-perf/)