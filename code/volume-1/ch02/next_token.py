"""Chapter 2 demo: a language model predicts one token at a time, and picks from a probability distribution."""

import math
import sys

from agentlab.llm import chat


def show_next_token_probabilities(prompt: str) -> None:
    response = chat([{"role": "user", "content": prompt}], max_tokens=1, logprobs=True, top_logprobs=5)
    print(f"Prompt: {prompt}\nTop five candidates for the first token of the reply:")
    for candidate in response.choices[0].logprobs.content[0].top_logprobs:
        print(f"  {candidate.token!r:>14}  {math.exp(candidate.logprob):6.1%}")


def ask_three_times(prompt: str, temperature: float) -> None:
    print(f"\nThree calls at temperature={temperature}:")
    for i in range(1, 4):
        response = chat([{"role": "user", "content": prompt}], temperature=temperature, max_tokens=60)
        print(f"  {i}. {response.choices[0].message.content.strip()}")


if len(sys.argv) > 1:
    question = sys.argv[1]
else:
    question = "In one short sentence, why might a shipment be held at customs?"
    show_next_token_probabilities("Complete the sentence with one word: Shipment SH-4471 is held at")
show_next_token_probabilities(question)
print(f"\nPrompt: {question}")
ask_three_times(question, temperature=1.0)
ask_three_times(question, temperature=0.0)
