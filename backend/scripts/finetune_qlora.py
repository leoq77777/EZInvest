"""QLoRA 4-bit fine-tuning script for Qwen2.5-7B on financial QA data.

Usage:
    python scripts/finetune_qlora.py \
        --base_model Qwen/Qwen2.5-7B \
        --dataset data/processed/financial_qa.jsonl \
        --output_dir models/finetuned/qwen2.5-7b-qlora \
        --epochs 3 \
        --batch_size 4
"""

import argparse
import json
import logging
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from trl import SFTTrainer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_dataset_from_jsonl(path: str) -> Dataset:
    """Load a JSONL dataset with 'instruction', 'input', 'output' fields."""
    records = []
    with open(path) as f:
        for line in f:
            records.append(json.loads(line))
    return Dataset.from_list(records)


def format_prompt(example: dict) -> dict:
    """Format into chat template for instruction tuning."""
    instruction = example.get("instruction", "")
    inp = example.get("input", "")
    output = example.get("output", "")

    if inp:
        text = (
            f"<|im_start|>system\nYou are a financial analysis expert.<|im_end|>\n"
            f"<|im_start|>user\n{instruction}\n\nContext: {inp}<|im_end|>\n"
            f"<|im_start|>assistant\n{output}<|im_end|>"
        )
    else:
        text = (
            f"<|im_start|>system\nYou are a financial analysis expert.<|im_end|>\n"
            f"<|im_start|>user\n{instruction}<|im_end|>\n"
            f"<|im_start|>assistant\n{output}<|im_end|>"
        )
    return {"text": text}


def main(args):
    logger.info("Loading base model: %s", args.base_model)

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)

    tokenizer = AutoTokenizer.from_pretrained(
        args.base_model, trust_remote_code=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    lora_config = LoraConfig(
        r=64,
        lora_alpha=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)

    trainable, total = model.get_nb_trainable_parameters()
    logger.info(
        "Trainable params: %d / %d (%.2f%%)",
        trainable, total, 100 * trainable / total,
    )

    logger.info("Loading dataset: %s", args.dataset)
    dataset = load_dataset_from_jsonl(args.dataset)
    dataset = dataset.map(format_prompt, remove_columns=dataset.column_names)
    logger.info("Dataset size: %d examples", len(dataset))

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        logging_steps=10,
        save_strategy="epoch",
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        optim="paged_adamw_8bit",
        report_to="none",
        max_grad_norm=0.3,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=training_args,
        max_seq_length=2048,
    )

    logger.info("Starting fine-tuning...")
    trainer.train()

    logger.info("Saving model to %s", args.output_dir)
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    logger.info("Fine-tuning complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QLoRA fine-tuning for financial LLM")
    parser.add_argument("--base_model", type=str, default="Qwen/Qwen2.5-7B")
    parser.add_argument("--dataset", type=str, required=True)
    parser.add_argument("--output_dir", type=str, default="models/finetuned/qwen2.5-7b-qlora")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch_size", type=int, default=4)
    main(parser.parse_args())
