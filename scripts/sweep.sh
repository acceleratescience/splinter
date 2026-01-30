#!/bin/bash

# --- CONFIGURATION ---
API_URL="https://whatever-url.net"  # Change to your endpoint
MODEL_NAME="openai/gpt-oss-120b"                         # Change to your model name
OUTPUT_DIR="./bench_results_$(date +%Y%m%d_%H%M%S)"
# The rates we want to test (Requests per Second)
CONCURRENCY_RATES=(16 32 64 96 128 192 256 384 512)
# Number of prompts to send per test (Higher = more stable data)
NUM_PROMPTS=512

mkdir -p "$OUTPUT_DIR"

echo "--------------------------------------------------------"
echo "Starting Capacity Sweep against: $API_URL"
echo "Model: $MODEL_NAME"
echo "--------------------------------------------------------"

# --- THE SWEEP LOOP ---
for RATE in "${CONCURRENCY_RATES[@]}"; do
    echo "Testing Concurrency: $RATE ..."
    
    # Run the vLLM benchmark tool
    vllm bench serve \
        --backend vllm \
        --base-url "$API_URL" \
        --model "$MODEL_NAME" \
        --endpoint /v1/completions \
        --dataset-name sharegpt \
        --dataset-path ShareGPT_V3_unfiltered_cleaned_split.json \
        --num-prompts "$NUM_PROMPTS" \
        --max-concurrency "$RATE" \
        --save-result \
        --save-detailed \
        --result-dir "$OUTPUT_DIR" \
        --result-filename "rate_${RATE}.json"
    
    echo "Finished $RATE req/s. Result saved."
    echo "--------------------------------------------------------"
done

echo "Sweep complete! Results are in $OUTPUT_DIR"
