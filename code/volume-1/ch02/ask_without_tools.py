"""Chapter 2 demo: ask about a company-specific shipment with no tools. The model has never seen the data."""

import sys

from agentlab.llm import chat

question = sys.argv[1] if len(sys.argv) > 1 else "Why is shipment SH-4471 late?"
reply = chat([{"role": "user", "content": question}]).choices[0].message
print(f"Prompt: {question}\n\nReply:\n{reply.content}")
