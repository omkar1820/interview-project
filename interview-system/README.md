# Automated Candidate Interview & Evaluation System

AI-powered multi-agent first-round interview platform.
**Stack:** Python 3.11 · FastAPI · WebSocket · AutoGen · NLP (TF-IDF) · OpenAI GPT · MySQL on **AWS RDS** · Docker · Jenkins · Terraform

```
Browser --WebSocket--> FastAPI --> AutoGen agents (Interviewer, Candidate Proxy, Evaluator) --> OpenAI GPT
                          |
                          +--> MySQL (AWS RDS): candidates, interviews, responses (questions+scores), final_results
```

## How it works
1. Recruiter creates an interview (`/`) and sends the candidate link `/interview?id=..&token=..`.
2. Over a WebSocket, the **Interviewer Agent** asks a question (follow-ups use earlier answers).
3. The **Candidate Proxy** relays the answer; the **Evaluator Agent** blends NLP (TF-IDF cosine relevance, communication and
   reasoning heuristics) with an LLM judgement into technical / relevance / problem-solving / communication scores + feedback.
4. Each Q&A + score is saved to MySQL; the loop repeats. At the end a `final_results` row holds averages, strengths,
   improvements and a recommendation.
5. Recruiters review everything on `/dashboard` and record their own decision (advance/hold/reject). AI is decision support only.

Without `OPENAI_API_KEY` (or with `LLM_MODE=mock`) the system runs offline using question banks + NLP heuristics, so you can
test the whole pipeline for free. Candidates do not see scores; only recruiters do.

## Project layout
```
app/            FastAPI app, models, agents, NLP, static UI
tests/          pytest (NLP + full interview flow over WebSocket, SQLite)
Dockerfile      multi-stage: base -> test (flake8+pytest) -> runtime
docker-compose.yml
Jenkinsfile     test -> build -> scan -> push ECR -> deploy EC2 -> smoke test
terraform/      RDS MySQL, ECR, EC2, security groups, IAM, Secrets Manager
scripts/deploy.sh   runs on EC2: pulls image, loads secrets, health-check + rollback
```

## 1. Run locally (no AWS needed)
```bash
pip install -r requirements.txt
LLM_MODE=mock DATABASE_URL=sqlite:///./local.db uvicorn app.main:app --reload
# open http://localhost:8000   (API docs: /docs)
```
Local MySQL in Docker: `cp .env.example .env`, set `DB_HOST=db`, `DB_SSL_CA=`, then
`docker compose --profile local-db up --build`.

## 2. Provision AWS (Terraform)
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # fill in VPC, subnets, key pair, Jenkins IP, OpenAI key
terraform init && terraform apply
```
Creates: RDS MySQL 8.0 (encrypted, private, 7-day backups), security groups (DB reachable only from the app server),
ECR repo, EC2 app server with IAM role (ECR pull + read two secrets), and Secrets Manager entries
`interview-eval/db` (host/user/password) and `interview-eval/app` (OpenAI key, generated admin API key).
Get the recruiter key: `aws secretsmanager get-secret-value --secret-id interview-eval/app --query SecretString`.

Notes: the RDS password lives in Terraform state - use an encrypted remote backend (S3 + DynamoDB lock) for real use.
Tables are auto-created on startup (`create_all`); add Alembic migrations before evolving the schema in production.

## 3. Jenkins pipeline
Create a Pipeline job from SCM pointing at this repo (uses `Jenkinsfile`). Jenkins agent needs Docker, AWS CLI, ssh
(optionally `trivy`). Add credentials: `aws-jenkins`, `aws-account-id`, `ec2-deploy-key`,
`deploy-host-staging`, `deploy-host-production` (EC2 IP from `terraform output app_public_ip`).
Stages: Checkout -> Lint & Test (Docker `test` target) -> Build -> Trivy scan -> Push to ECR -> (prod approval) ->
Deploy over SSH (`scripts/deploy.sh`, auto-rollback on failed health check) -> Smoke test `/health`.
Adjust `AWS_REGION` (default `ap-south-1`) in the Jenkinsfile if needed.

## API
| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | /api/interviews | X-API-Key | create candidate + interview, returns link |
| GET | /api/interviews | X-API-Key | list with scores |
| GET | /api/interviews/{id}/report | X-API-Key | full report |
| PATCH | /api/interviews/{id}/decision | X-API-Key | recruiter decision |
| GET | /api/interviews/{id}/public?token= | token | candidate page info |
| WS | /ws/interview/{id}?token= | token | live interview |
| GET | /health | - | DB-aware health check |

## Config (env vars)
`DB_HOST DB_PORT DB_USER DB_PASSWORD DB_NAME DB_SSL_CA` (or `DATABASE_URL`), `OPENAI_API_KEY`, `OPENAI_MODEL`,
`LLM_MODE` (auto|openai|mock), `ADMIN_API_KEY`, `DEFAULT_NUM_QUESTIONS`, `ANSWER_TIMEOUT_SECONDS`.

## Responsible use
Automated screening of people is regulated in many places and can encode bias. Tell candidates an AI is used and get
consent, keep humans in the decision loop (built in), audit scores for disparate impact, and set a data-retention policy
for answers stored in the database.

## Known limits
- Evaluator weights/thresholds (`evaluator.py`, `scoring.py`) are reasonable defaults, not validated hiring science.
- AutoGen `ConversableAgent` powers the Interviewer and Evaluator; the Candidate Proxy is a plain WebSocket bridge class.
- Terraform and the Jenkinsfile were written but not run here (no AWS/Jenkins in my sandbox); tests and lint were run.
