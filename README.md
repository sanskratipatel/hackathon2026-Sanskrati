<!-- # hackathon2026-Sanskrati  
# 🤖 ShopWave AI Support Resolution Agent

Production-grade autonomous customer support agent built for **Agentic AI Hackathon 2026**.

This system processes support tickets end-to-end using:

✅ Deterministic policy engine  
✅ Tool calling on JSON data  
✅ Knowledge base retrieval  
✅ Open-source LLM reasoning  
✅ Fraud detection  
✅ Confidence scoring  
✅ Escalation logic  
✅ Full audit logs  
✅ Beautiful Streamlit dashboard  
✅ Concurrent batch processing

---

# 🚀 Features

## Ticket Types Supported

- Refund Requests
- Return Requests
- Cancellation
- Warranty Claims
- Wrong Item Delivered
- Damaged Product
- VIP Claim Validation
- Fraud Signals
- Missing Order Info
- Exchange Requests

---

# 🧠 Architecture

Deterministic systems first. LLM second.

```text
Ticket
 ↓
Tool Calls
(customer/order/product)
 ↓
Knowledge Base Search
 ↓
Policy Engine
 ↓
Critic Review Pass
 ↓
LLM Reply Generator
 ↓
Confidence Score
 ↓
Audit Logs + Results --> 
# Hackathon 2026 - AI Support Agent

## Project Overview

This project is an AI-powered customer support agent designed to automate ticket resolution using a hybrid system of deterministic policy engine + tool-based reasoning + LLM response generation.

The system processes customer tickets, retrieves order/customer/product data, runs business rule engines, evaluates fraud risk, and generates a final response.

It is designed to be reliable, explainable, and production-ready for real-world support workflows.

---

## Tech Stack

- Python 3.10+
- Groq API (LLM inference)
- REST APIs (requests)
- JSON-based data pipeline
- Concurrent processing (ThreadPoolExecutor)
- Rule-based policy engine
- Logging + audit system

---

## Project Structure

hackathon2026-yourname/
│── app.py
│── requirements.txt
│── README.md
│── failure_modes.md
│── architecture.md
│── audit_log.json
│── .env
│
├── data/
│   ├── tickets.json
│   ├── orders.json
│   ├── customers.json
│   ├── products.json
│
├── src/
│   ├── config.py
│   ├── tools.py
│   ├── kb.py
│   ├── policy.py
│   ├── logger.py
│   ├── workflow.py
│   ├── agent.py
│   ├── llm.py
│   └── utils.py



---

## How to Run the Project

### Step 1: Install dependencies

```bash
pip install -r requirements.txt 


Step 2: Setup environment variables

Create a .env file:

GROQ_API_KEY=your_api_key_here
MODEL_NAME=llama3-8b-8192
ENV=dev
LOG_LEVEL=INFO
REQUEST_TIMEOUT=20
MAX_RETRIES=3 


Step 3: Run the agent

streamlit run app.py 

This will:

Load all tickets from data/tickets.json
Process them using workflow engine
Run tools (customer, order, product, fraud, warranty, etc.)
Apply policy engine
Call LLM for final response
Save results to outputs/results.json
Generate audit logs 


System Design

The system follows a layered architecture:

Input Layer (tickets.json)
Customer/Order/Product resolution layer
Tool execution layer (fraud, refund, warranty, return window)
Policy engine (deterministic rules)
Critic validation layer
Confidence scoring system
LLM response generator (Groq API)
Audit logging layer 


Key Features
Deterministic-first decision system
Fallback-safe LLM integration
Parallel ticket processing
Fraud detection layer
Return/refund/warranty policy engine
Confidence scoring mechanism
Full audit trail for every decision
Failure Handling

The system is designed to gracefully degrade:

Missing customer → Escalate
Missing order → Escalate or fallback lookup via email
Tool failure → Safe empty response
LLM failure → Rule-based fallback response
Invalid JSON → Safe parser fallback
