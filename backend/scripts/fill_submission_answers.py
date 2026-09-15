#!/usr/bin/env python3
import argparse
import asyncio
import json
from pathlib import Path

import httpx


async def answer_question(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    item: dict,
    total: int,
) -> tuple[int, str]:
    number = int(item["question_number"])
    async with semaphore:
        for attempt in range(3):
            try:
                response = await client.post(
                    "/api/chat",
                    json={
                        "message": item["question"],
                        "document_ids": [],
                        "filters": {
                            "file_types": [],
                            "technologies": [],
                            "industries": [],
                        },
                        "conversation_id": None,
                        "history": [],
                    },
                )
                response.raise_for_status()
                answer = response.json()["answer"].strip()
                print(f"[{number:02}/{total}] answered")
                return number, answer
            except (httpx.HTTPError, KeyError) as error:
                if attempt == 2:
                    raise RuntimeError(
                        f"Question {number} failed after 3 attempts: {error}"
                    ) from error
                await asyncio.sleep(1.5 * (attempt + 1))
    raise AssertionError("unreachable")


async def run(input_path: Path, output_path: Path, api_base_url: str) -> None:
    submission = json.loads(input_path.read_text(encoding="utf-8"))
    answers = submission.get("answers")
    if not isinstance(answers, list) or not answers:
        raise ValueError("Input JSON must contain a non-empty answers array")
    if any("question" not in item or "answer" not in item for item in answers):
        raise ValueError("Every answer item must contain question and answer fields")

    timeout = httpx.Timeout(180.0, connect=10.0)
    semaphore = asyncio.Semaphore(4)
    async with httpx.AsyncClient(base_url=api_base_url, timeout=timeout) as client:
        health = await client.get("/api/health")
        health.raise_for_status()
        results = await asyncio.gather(*[
            answer_question(client, semaphore, item, len(answers))
            for item in answers
        ])

    by_number = dict(results)
    for item in answers:
        item["answer"] = by_number[int(item["question_number"])]
    output_path.write_text(
        json.dumps(submission, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Completed {len(answers)} answers: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fill a PIH participant submission by calling the running API."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--api-base-url",
        default="http://127.0.0.1:8000",
    )
    args = parser.parse_args()
    asyncio.run(run(args.input.resolve(), args.output.resolve(), args.api_base_url))


if __name__ == "__main__":
    main()
