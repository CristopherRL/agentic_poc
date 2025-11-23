# Agentic Assistant Challenge

## Business Goal

Build a basic agentic assistant that can answer user questions by drawing from:

1. Structured data (CSV tables provided), via generated SQL
2. Unstructured documents (PDF contracts provided), via a lightweight RAG pipeline
3. Owner's manuals from https://www.toyota-europe.com/customer/manuals, by extracting a small sample and enriching your document index. Add these manuals to your RAG index so the assistant can answer basic owner's manual questions (e.g., maintenance intervals, feature explanations).

Automated fetch would be preferred, but if pressed by time, manual download of sample PDFs/sections is fine—explain how you'd productionize responsibly (API, license or data partnership).

The assistant should decide which tool(s) to use per question (SQL vs RAG vs both), execute, and return an answer with citations and the SQL used (when applicable). A minimal interface is expected to demonstrate a few example questions end-to-end.

## Scope & Expectations

* Keep each component small but real: safe SQL execution, a tiny RAG index over a few PDFs/manuals and a simple decision policy (rule-based or LLM-guided) for tool selection.
* Show an architecture diagram and capture key trade-offs (latency, cost, security, maintainability).

## Provided Starter Data

Use the bundled CSVs and PDFs (we'll share them separately):

* CSVs: DIM_MODEL, DIM_COUNTRY, DIM_ORDERTYPE, FACT_SALES, FACT_SALES_ORDERTYPE
* PDFs: Contract_Toyota_2023.pdf, Contract_Lexus_2023.pdf, Warranty_Policy_Appendix.pdf

You may load CSVs into a local SQLite/DuckDB/Postgres—your choice.

## Agent Orchestration

* A simple router that picks between:
  * SQL Tool → for questions about sales, time, country/region, model, powertrain
  * RAG Tool → for questions about warranty terms, policy clauses, or owner's manual content
  * Hybrid → combines SQL + RAG when the question spans both (e.g., "Compare sales and summarize key warranty differences")
* Show a tool-use trace (which tools were called, with what inputs).

## Minimal Interface

* Simple CLI, Streamlit app, or small web UI:
  * Input box for a question
  * Display final answer

## Example Questions to Demonstrate

(these are used as guidance, they are not enforced – you can use similar questions)

1. SQL: "Monthly RAV4 HEV sales in Germany in 2024."
2. RAG (contracts/policy): "What is the standard Toyota warranty for Europe?"
3. RAG (owner's manual): "Where is the tire repair kit located for the UX?" (or similar simple manual fact)
4. Hybrid: "Compare Toyota vs Lexus SUV sales in Western Europe in 2024 and summarize any key warranty differences."
