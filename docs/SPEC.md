> Last reviewed: 2026-08-20 (documentation reconciliation migration).

## SPEC amendments

This document is normative and is **amended in place with a dated marker**, never by deleting
requirement text: a requirement that has been overtaken is *dated*, not removed. Each marker names
its decision id(s) or register key; the reasoning stays in `DECISIONS.md`. Markers added
**2026-08-20** (`AMENDMENT-SWEEP`, `RISK-R1.4-SPEC-VINTAGE`):

- **§5.2.2** — auth-option menu frozen, not chosen (D-152, `AUTH-OPTION-O1B`).
- **§5.5.2** — Topic Resolver is deterministic; Tutor Summary Generator uses the LLM report path (D-024).
- **§5.5.3** — `LearningState` shape: 36 listed fields versus 32 in code (`AMENDMENT-SWEEP`).
- **§5.8.1** — volume target is 5–7 per occupied tier, not 100 templates per topic (D-273 §2, D-223; parked by D-342).
- **§5.11.2** — priority rule 4 deliberately outranks rules 2–3, with the measurement (D-325).
- **§5.13** — post-exam composition is 10 total (D-302); the authored-item repeat is a knowing departure (D-189).
- **§5.15.2** — retention windows governed by D-333, including a chat clock this section has no row for.
- **§5.17** — solution images: requirement unchanged, feature **deferred and unbuilt** (D-078, `IMAGE-WORK-PARK`).
- **§5.19.3** — `QAState.ephemeral_location` does not exist; the code is right (`AMENDMENT-SWEEP`).
- **§5.19.5** — nine listed reasons versus ten in code, and an untyped client contract (fact, `AMENDMENT-SWEEP`).
- **§5.25.1** — Guardrails and gateway-level PII redaction are declared and never used (`REQ-32-SAFETY`, UD-9).
- **§5.25.3** — two of the thirteen artifact types (Topic mapping, Email draft) are declared and never used; both dispositioned deterministic (DRIFT-55, D-024, D-020).
- **§5.26.3** — internal NL2SQL is unbuilt and the decision is **open**, not superseded (`DRIFT-66-NL2SQL`, UD-12(d)).
- **§5.30.1** — the denylist holds; the allowlist describes one of 23 payloads, plus two payload facts (`AMENDMENT-SWEEP`).
- **§5.32.1** — the observability "choose one" fork is decided (D-214, D-242).
- **§5.33 / §5.33.4 / §5.36** — deployment substrate and scaling mechanisms are ECS/RDS, not EKS/Aurora/SQS (D-004, D-084).
- **§6** — demoted to **historical in place**; ROADMAP's per-session criteria superseded it.

Markers added **2026-08-20 by explicit user sign-off** (the two sections previously held pending):

- **§5.1.4** — "sensitive information in an email" is subsumed by `email_approval`, not a distinct unbuilt gate (DRIFT-16, Reading A).
- **§5.29** — the dead-letter queue and smaller-model fallback are removed as requirements (never built; reintroduction requires a new decision); coverage note: 4 of 19 rows sampled, 15 unverified (DRIFT-15/REQ-49, Option A).

Earlier markers, left as they stand: **§5.19.4** (amended 2026-08-15, D-351) and **§5.35**'s staging
MySQL note (D-092).

Marker added **2026-08-24** (the D-438 descriptive re-read, `TEST-05`):

- **§5.36** — two further cells: `Grafana` was decided otherwise (dashboards are CloudWatch, D-244;
  the Prometheus half is as built), and the `PostgreSQL` placement grew the cross-replica SSE event
  relay (`LISTEN`/`NOTIFY`, D-334/D-335/D-349).

# 5. Very Detailed Version

## 5.0 Document Purpose and Confirmed Design Principles

This system is an enterprise-level AI education platform designed for K–12 students across the United States, with minors as the primary user group. It consists of two independently deployed applications.

1. **Adaptive Learning Application**
   - Domain: `learning.intellichoice.org`
   - Users: Students and parents
   - Functions: Attendance verification, pre-exam, personalized study, post-exam, learning-gain analysis, and parent reports

2. **Organization Q&A Application**
   - Domain: `chat.intellichoice.org`
   - Users: Anonymous visitors, prospective volunteers, prospective students, parents, students, tutors, and branch managers
   - Functions: Document-based RAG, branch search, calendar generation, administrator escalation, and role-specific internal document retrieval

The two applications follow these principles:

- The frontend and backend of each application are deployed independently.
- Both applications reuse the existing authentication system from `go.intellichoice.org`.
- The existing MySQL remains the source of truth for users, roles, parent-child relationships, grade levels, branches, and attendance.
- The new PostgreSQL system stores only learning, question, assessment, memory, RAG, and checkpoint data.
- PostgreSQL with `pgvector` is used instead of introducing a separate vector database.
- Personally identifiable information such as names and email addresses is not copied from MySQL into PostgreSQL.
- LLMs are used for language-oriented tasks such as explanation, intent classification, summarization, and question-template generation.
- Attendance verification, authorization, score calculation, multiple-choice grading, and SQL execution are handled deterministically.
- Student solution images are deleted immediately after multimodal analysis.
- The initial production release supports English only.
- The initial production architecture targets more than 1,000 students and more than 100 concurrent learning sessions.
- The initial monthly availability SLO is 99.9%.

---

## 5.1 Legal, Privacy, and User Consent Design

### 5.1.1 Potentially Applicable Laws

Because the product serves minors across the United States, the organization should evaluate the applicability of at least the following:

- COPPA
- FERPA
- PPRA
- State-level student privacy laws
- State-level consumer privacy laws
- Data breach notification laws
- Contractual privacy obligations when working with schools or educational institutions

COPPA may apply to online services directed to children under 13 or to services that knowingly collect personal information from children under 13. It requires parental notice and verifiable parental consent. The FTC amended the COPPA Rule on April 22, 2025, so the production release should be reviewed against the updated rule.  
Source: [FTC COPPA Rule](https://www.ftc.gov/legal-library/browse/rules/childrens-online-privacy-protection-rule-coppa)

FERPA gives parents certain rights regarding access to, amendment of, and disclosure of student education records. Those rights may transfer to the student when the student turns 18 or attends a postsecondary institution. Whether IntelliChoice itself is directly subject to FERPA, or acts as a service provider to a covered institution, depends on the organization’s legal structure and contractual relationships.  
Source: [U.S. Department of Education — What is FERPA?](https://studentprivacy.ed.gov/faq/what-ferpa)

If a school or educational institution provides student records to IntelliChoice under the FERPA school-official exception, the service should operate under the institution’s direct control, use the data only for authorized educational purposes, and restrict redisclosure.  
Source: [U.S. Department of Education — School Official Under FERPA](https://studentprivacy.ed.gov/faq/who-school-official-under-ferpa)

The legal sections in this document define product requirements and do not constitute legal advice. Review by U.S. education and child-privacy counsel should be a mandatory production release gate.

---

### 5.1.2 Existing Account System and Product-Specific Consent

Account creation, direct student registration, parent-created accounts, parent-child linking, and COPPA parental consent are assumed to be handled by the existing `go.intellichoice.org` system.

However, the first visit to `learning.intellichoice.org` should present a product-specific Adaptive Learning notice.

The notice should explain:

- AI analyzes student answers and learning history.
- AI-generated hints and explanations may contain errors.
- AI does not replace a teacher or tutor.
- Pre-exam and post-exam results are used to adjust the student’s estimated level.
- Scores and skills to strengthen may be shared in limited form with tutors and branch managers.
- Parents can view the child’s complete learning record and automatically generated reports.
- Student questions and learning events may be used to create learning memory.
- Uploaded solution images are deleted immediately after analysis.
- External YouTube learning resources may be recommended.
- Data sent to external AI, AWS, and observability systems is minimized and de-identified where possible.
- Students can challenge learning results or report problematic questions.

The existing authentication token should contain at least:

```text
sub
role
account_status
consent_status
parental_consent_verified
consent_version
student_age_band
issued_at
expires_at
audience
```

`learning.intellichoice.org` must not use a student-facing notice as a substitute for parental consent for users under 13. It should verify `parental_consent_verified=true` from the existing system and then present an age-appropriate notice to the student.

---

### 5.1.3 Location Consent

Before using the Branch Locator, display:

```text
Your location will be used only to calculate nearby IntelliChoice branches.
IntelliChoice will not permanently store your precise location.
```

Processing rules:

- Request browser geolocation only after explicit permission.
- Discard precise coordinates after the Google Maps MCP request completes.
- Do not store precise coordinates in PostgreSQL, MySQL, LangSmith, or application logs.
- Allow users to enter a ZIP code, city, or address instead.
- Do not retain the raw manually entered address by default.

---

### 5.1.4 Consent for External Actions

> **Amended 2026-08-20 by user sign-off (DRIFT-16).** Of the six enumerated actions,
> five are gated by existing interrupt classes; image analysis has no feature to
> gate (deferred, D-078). "Potentially sensitive information in an email" is read
> as subsumed by the `email_approval` interrupt — every outbound email requires human
> approval with the full preview visible, and free text is redacted unconditionally
> before the node — not as a distinct, never-built sensitivity gate. No second
> sensitivity-specific approval gate is required.

Explicit approval is required before:

- Sending an attendance-verification email to a branch manager
- Sending a question to an administrator
- Creating a Google Calendar event
- Using the user’s location
- Analyzing an uploaded solution image
- Including potentially sensitive information in an email

LangGraph `interrupt()` is used to implement human approval.

---

### 5.1.5 Prohibited Data Uses

The following are prohibited:

- Selling student data
- Behavioral advertising directed at students
- Using scores or weaknesses for marketing
- Using student data for unauthorized model training
- Retaining images for facial recognition
- Retaining precise location history
- Sending email or creating calendar events without approval
- Exposing complete chat transcripts to tutors or branch managers

---

## 5.2 Subdomains and Independent Deployment

### 5.2.1 Deployment Units

```text
learning.intellichoice.org
├── Learning Frontend
├── Learning FastAPI
├── Learning LangGraph
├── Assessment Service
├── Learning Memory Service
└── Parent Report Service

chat.intellichoice.org
├── Q&A Frontend
├── Q&A FastAPI
├── Q&A LangGraph
├── RAG Service
├── MCP Tool Gateway
└── Escalation Service
```

Each application has its own:

- GitHub Actions workflow
- Docker image
- Helm release
- Kubernetes namespace
- Kubernetes deployment
- Horizontal Pod Autoscaler
- Domain and TLS certificate
- Application configuration
- Release version
- Rollback boundary

Shared components:

- Existing authentication authority
- MySQL Profile Adapter
- Aurora PostgreSQL cluster
- AWS Bedrock Gateway
- LangSmith
- OpenTelemetry Collector
- Prometheus and Grafana
- Secrets Manager
- Shared Pydantic schema package
- Shared tool-security policy

---

### 5.2.2 Shared Authentication

**Frozen 2026-08-20 (D-152; `AUTH-OPTION-O1B`) — nothing below is finalized.** The option menu at the
end of this section is **not yet chosen, and choosing it is deliberately deferred**. `S42_DISCOVERY.md`
§8 recommends **O1b** (a server-side call to the existing login endpoint, a transient header-borne
legacy token for the profile/attendance reads, then this stack minting its own §5.1.2 token) with
**O2** (HMAC re-verification) as the documented fallback — and calls itself a recommendation, not a
decision. It **stays a recommendation until measured, immediately before S44**. The evidence it needs
— AWS→icrest reachability, and confirming the deployed build matches the checkout — is exactly what
D-152 forbids measuring now. Every requirement below (application-specific audiences, short-lived
codes, blast-radius containment) still binds whichever option is finally taken.

The applications should share the login experience without exposing one broad session cookie to every subdomain.

Recommended flow:

```text
User logs in at go.intellichoice.org
    ↓
Central Authentication Service
    ↓
Short-lived authorization code
    ↓
learning.intellichoice.org or chat.intellichoice.org
    ↓
Application-specific access token
```

Application-specific audiences:

```text
audience = learning
audience = chat
audience = go
```

This limits the blast radius if one subdomain is compromised.

If the existing authentication system does not support OIDC, implement one of:

- Signed JWT token exchange
- One-time authorization code
- Backend-to-backend session validation
- Short-lived application token

---

## 5.3 Enterprise Architecture

```text
Users
│
├── go.intellichoice.org
├── learning.intellichoice.org
└── chat.intellichoice.org
        │
CloudFront + AWS WAF
        │
Application Load Balancer
        │
Amazon EKS
├── Learning Namespace
│   ├── Learning Frontend
│   ├── Learning FastAPI
│   ├── Learning Worker
│   └── Learning LangGraph
│
├── Chat Namespace
│   ├── Chat Frontend
│   ├── Chat FastAPI
│   ├── RAG Worker
│   └── Chat LangGraph
│
├── Shared Services Namespace
│   ├── Bedrock Gateway
│   ├── MCP Gateway
│   ├── Profile Adapter
│   ├── Evaluation Runner
│   └── OpenTelemetry Collector
│
├── Existing MySQL
│   ├── Users
│   ├── Roles
│   ├── Parent-Child Relationships
│   ├── Grade
│   ├── Branch
│   └── Attendance
│
├── Aurora PostgreSQL
│   ├── Learning Database
│   ├── Q&A/RAG Database
│   ├── pgvector
│   ├── Memory
│   └── LangGraph Checkpoints
│
├── Amazon S3
│   ├── RAG Source Documents
│   ├── RAG Processed Artifacts
│   ├── Private Generated Reports
│   └── Temporary Upload Area
│
└── External Services
    ├── AWS Bedrock
    ├── Gmail MCP
    ├── Google Maps MCP
    ├── Google Calendar MCP
    └── YouTube Data API
```

Aurora PostgreSQL supports `pgvector`, allowing relational data and vector embeddings to be managed in the same database tier.  
Source: [AWS Aurora PostgreSQL as a Vector Database](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.VectorDB.html)

The system uses a custom LlamaIndex-based RAG pipeline instead of delegating the entire retrieval layer to Bedrock Knowledge Bases. This preserves control over chunking, hybrid search, metadata filtering, reranking, and citation validation.

---

## 5.4 MySQL and PostgreSQL Responsibility Separation

### 5.4.1 MySQL as the Source of Truth

MySQL stores:

- User name
- Email
- Role
- Parent-child relationship
- Student grade
- Student branch
- Branch manager email
- Attendance
- Account status

PostgreSQL stores only MySQL primary keys or shared external identifiers:

```text
student_external_id
parent_external_id
branch_external_id
user_external_id
```

Do not replicate into PostgreSQL:

- Student names
- Parent names
- Email addresses
- Phone numbers
- Addresses
- Full MySQL user rows

---

### 5.4.2 PostgreSQL as the Source of Truth

PostgreSQL stores:

- Curriculum topics
- Skills
- Question templates
- Generated question variants
- Pre-exam and post-exam sessions
- Study sessions
- Student attempts
- Scores
- Mastery
- Learning gain
- Hint usage
- Video usage
- Skills to strengthen
- Episodic memory
- Semantic memory
- Weekly reports
- RAG document metadata
- RAG chunks
- Embeddings
- LangGraph checkpoints
- Evaluation results
- Problem reports and quarantine status

---

### 5.4.3 Combining MySQL and PostgreSQL Results

Do not attempt a direct operational SQL join across MySQL and PostgreSQL.

Instead, combine results in the FastAPI service layer:

```text
Request
  ↓
Authorization Context
  ↓
Async parallel fetch
  ├── MySQL: name, role, grade, branch, attendance
  └── PostgreSQL: score, mastery, learning history
  ↓
Join by external primary key
  ↓
Response DTO
```

Example:

```python
profile, learning = await asyncio.gather(
    mysql_profile_adapter.get_student_profile(student_id),
    postgres_learning_repository.get_summary(student_id),
)

return StudentLearningView(
    student_id=student_id,
    display_name=profile.display_name,
    grade=profile.grade,
    attendance=profile.attendance,
    scores=learning.scores,
    weak_skills=learning.weak_skills,
)
```

Benefits:

- Preserves MySQL as the source of truth
- Avoids PII duplication
- Reduces consistency issues
- Clarifies database responsibility
- Avoids operational federated-query dependencies

If large-scale analytics becomes necessary, use a separate de-identified analytics warehouse rather than copying MySQL PII into the operational PostgreSQL database.

---

### 5.4.4 Real-Time Attendance Lookup

Attendance is read directly from MySQL when the learning session begins.

```text
Start Learning
  ↓
Read user and child relationship from MySQL
  ↓
Read current-week attendance from MySQL
  ↓
Present / Absent / Unknown
```

Do not assume `present` when MySQL is unavailable.

Display:

```text
We could not verify attendance at this time.
For student safety and record accuracy, the learning session cannot begin
until attendance is confirmed.
```

---

## 5.5 Adaptive Learning LangGraph

### 5.5.1 Full Workflow

```text
START
  ↓
Authenticate User
  ↓
Load MySQL Profile
  ↓
Resolve Student
  ├── Student account → Use current student
  └── Parent account
       ├── One child → Auto-select
       └── Multiple children → Child Selection interrupt()
  ↓
Check Product Notice
  ↓
Check Attendance
  ├── Present → Select Topics
  ├── Absent → Attendance Resolution
  └── Unknown → Attendance Resolution
  ↓
Pre-exam
  ↓
Mastery Estimation
  ↓
Study Plan Generation
  ↓
Personalized Study
  ↓
Post-exam
  ↓
Learning Gain Calculation
  ↓
Update Memory
  ↓
Generate Parent Report
  ↓
Publish Tutor/Manager Summary
  ↓
END
```

---

### 5.5.2 Multi-Agent Components

**Amended 2026-08-20 (D-024; `AMENDMENT-SWEEP`).** Two rows below no longer describe the build.
**Topic Resolver** is a **deterministic node**, not "Structured LLM": `topic_resolver.py` is a plain
database lookup (question variant → template → topic/skill/mastery) and never calls an LLM, because no
endpoint accepts free text — an LLM free-text resolver gets added when a free-text endpoint first
needs one (D-024). **Tutor Summary Generator** is not a "Structured service": it uses the same LLM
report path as the Parent Report Agent. The rule under the table is unchanged and still binding —
grading, attendance, authorization and score calculation remain deterministic, and this amendment
moves one row *toward* determinism, not away from it.

| Component | Type | Responsibility |
|---|---|---|
| Learning Orchestrator | LangGraph | Controls the overall learning workflow |
| Profile Resolver | Deterministic node | Reads role and parent-child relationships from MySQL |
| Attendance Gate | Deterministic node | Reads attendance from MySQL |
| Attendance Escalation Agent | Tool agent | Creates branch-manager email drafts |
| Topic Resolver | Structured LLM | Maps student input to curriculum topics |
| Assessment Manager | Subgraph | Manages pre-exam and post-exam |
| Grading Node | Deterministic | Grades multiple-choice answers |
| Mastery Estimator | Statistical service | Estimates level and skills to strengthen |
| Study Planner | Rule + statistical | Selects five base study questions |
| Tutor Agent | LLM agent | Answers student follow-up questions |
| Intervention Router | Conditional node | Routes to hint, solution, or video |
| Video Catalog Tool | Retrieval tool | Searches the pre-synchronized video catalog |
| Learning Gain Service | Deterministic | Compares pre-exam and post-exam |
| Memory Consolidator | Agent + validator | Updates weekly semantic memory |
| Parent Report Agent | Structured LLM | Generates parent reports |
| Tutor Summary Generator | Structured service | Shares only scores and skill summaries |

Do not turn every node into an agent. Grading, attendance, authorization, and score calculation remain deterministic.

---

### 5.5.3 Learning State

**Amended 2026-08-20 (`AMENDMENT-SWEEP`).** The list below names **36** fields; an AST parse of
`apps/learning-api/src/learning_api/graph/state.py` counts **32** on `LearningState`, and the two
sets share only **eight** names — several are renamed (`current_topic_id` → `topic_id`,
`current_phase` → `phase`) and the code carries fields this list never had (the three
`*_session_id`s, the `last_*` family, the `stage_narrative_*` family, `bedrock_spend_cents`). The
code is the record of the shape. What still binds is the sentence after the list, which is a
requirement and not a shape: **names and email addresses are never stored in graph state.**

```text
LearningState
- user_external_id
- user_role
- student_external_id
- parent_external_id
- branch_external_id
- grade
- week_id
- session_id
- attendance_status
- attendance_resolution
- selected_topics
- current_phase
- current_topic_id
- current_skill_id
- assessment_type
- current_question_id
- current_question_index
- selected_answer
- correct_answer_id
- is_correct
- attempt_count
- intervention_choice
- hint_count
- solution_count
- video_count
- estimated_theta
- estimated_level
- mastery_by_skill
- weak_skills
- completed_problem_count
- total_problem_count
- pre_exam_result
- post_exam_result
- learning_gain
- pending_interrupt
- trace_id
```

Names and email addresses are not stored in graph state. Email addresses are retrieved temporarily from MySQL only when needed.

---

## 5.6 Parent Accounts, Child Selection, and Attendance Verification

### 5.6.1 Child Selection

A parent selects the child at the beginning of each learning session.

```text
Parent starts learning
  ↓
MySQL children lookup
  ├── 0 children → Error and support guidance
  ├── 1 child → Skip selection
  └── 2+ children → Show child selector
```

The selector may display:

- Child display name
- Grade
- Branch
- Current week
- Recent learning status

The backend must independently verify the parent-child relationship rather than trusting the submitted `student_id`.

---

### 5.6.2 Present Attendance

```text
attendance_status = present
→ Continue to topic selection
```

The attendance record must match the current week.

```text
student_id
branch_id
week_id
attendance_date
attendance_status
```

Attendance from a previous week cannot be reused.

---

### 5.6.3 Absent or Unknown Attendance

Offer two choices:

1. Ask the Branch Manager to verify attendance.
2. Acknowledge that the student did not attend.

Display:

```text
Attendance has not been confirmed for this week.

This learning sequence is connected to the material taught during the
student's on-site session. To prevent the student from being assessed on
material they did not receive, the session cannot continue until attendance
is confirmed.

You may ask the Branch Manager to verify the attendance record, or confirm
that the student did not attend this week.
```

---

### 5.6.4 Branch Manager Attendance Email

```text
Absent or Unknown
  ↓
Load Branch Manager email from MySQL
  ↓
Create email draft
  ↓
Show recipient, subject and body
  ↓
LangGraph interrupt()
  ↓
User approves
  ↓
Gmail MCP sends email
  ↓
Session remains blocked
```

Suggested email:

```text
Subject:
Attendance verification request for the week of [date]

Body:
A student or parent attempted to begin the weekly learning activity,
but the attendance record could not be confirmed.

Student: [display name]
Grade: [grade]
Week: [week]
Branch: [branch]

Please review the attendance record in the existing IntelliChoice system.
```

The system does not automatically parse the branch manager’s reply. The branch manager updates attendance in the existing system, and the user retries later.

---

### 5.6.5 Acknowledged Absence

When the user acknowledges the absence:

```text
attendance_resolution = absence_acknowledged
session_status = blocked_absent
```

PostgreSQL records only why the learning session was blocked:

```text
student_external_id
week_id
blocked_reason
blocked_at
```

Display:

```text
This week's adaptive learning activity is available only after attendance
because the assessment is based on the topics taught during the on-site
session.

Since the student did not attend, this learning sequence has ended.
No score or learning penalty will be recorded.
```

---

## 5.7 Kumon-Referenced Curriculum Taxonomy

### 5.7.1 Permitted Use

Do not copy official Kumon worksheets, wording, explanations, images, or private materials.

Permitted:

- Public level names
- Public topic names
- Public concept progression
- Reference use for an internal curriculum taxonomy

Not permitted:

- Reproducing official worksheets
- Creating derivative copies by changing only numbers
- Copying official explanations
- Implying official affiliation or certification
- Scraping private curriculum tables

Public Kumon materials describe progression from number sense and basic arithmetic through multiplication, division, fractions, algebraic expressions, equations, functions, graphs, factoring, quadratic equations, trigonometry, and calculus.  
Source: [Kumon Curriculum](https://www.kumon.com/resources/kumon-curriculum/)

---

### 5.7.2 Internal Curriculum Source

```text
repository/
└── curriculum/
    ├── kumon_us_reference/
    │   ├── curriculum_taxonomy.csv
    │   ├── curriculum_mapping.yaml
    │   ├── source_manifest.yaml
    │   └── README.md
    └── internal_math/
        ├── topics.yaml
        ├── skills.yaml
        ├── prerequisites.yaml
        └── grade_topic_mapping.yaml
```

Example `source_manifest.yaml`:

```yaml
source_name: "Kumon US public curriculum reference"
usage: "Level and topic taxonomy reference only"
official_affiliation: false
worksheet_content_copied: false
last_reviewed_at: "YYYY-MM-DD"
```

---

### 5.7.3 Initial Internal Topic Groups

| Grade Band | Internal Topic Group |
|---|---|
| K–1 | Number recognition, counting, number comparison, basic addition |
| 1–2 | Addition fluency, subtraction fluency, place value |
| 2–3 | Multi-digit operations, multiplication foundations |
| 3–4 | Multiplication, division, remainders, fractions |
| 4–5 | Fraction operations, decimals, order of operations |
| 5–6 | Ratios, percentages, signed numbers, expressions |
| 6–7 | Linear expressions, equations, inequalities |
| 7–8 | Systems, functions, graphs, exponents |
| 8–9 | Polynomials, factoring, quadratic foundations |
| 9–10 | Quadratic equations, functions, coordinate algebra |
| 10–11 | Advanced algebra, sequences, logarithms, trigonometry |
| 11–12 | Precalculus, limits, differentiation, integration foundations |

The student’s school grade narrows the initial topic candidates but does not determine the final learning level.

---

## 5.8 Question Bank and AI Generation/Review Pipeline

### 5.8.1 Question Volume

**Amended 2026-08-20 (D-273 §2, on D-223's measurement).** The **volume target of record is 5–7 items
per occupied tier** (~25–35 per topic, ~1,000 items across 34 topics), a deliberate divergence from
the 100 base templates per topic below (~3,400 items, roughly 3× the generation spend and review
burden). Two reasons, recorded by D-273: §5.8.1's number has never been met by any topic, and nothing
in the project has measured it as necessary, whereas 5–7 per tier was measured as the depth at which
exams stop repeating themselves. Not every `(skill, tier)` cell needs filling. All question-bank
coverage and depth work is currently **parked** by standing user instruction (D-342); 5–7 per tier is
the target when it resumes. *Citation note:* the 5–7 figure is stated **as a target by D-273**; D-223
measured it and does not state it as a target.

Each topic contains 100 validated base templates:

```text
Difficulty 1: 20 templates
Difficulty 2: 20 templates
Difficulty 3: 20 templates
Difficulty 4: 20 templates
Difficulty 5: 20 templates
```

Each template can generate multiple numerical variants.

Example:

```text
Template:
ax + b = c

Constraints:
a != 0
x is integer
distractors are unique
no division by zero
```

---

### 5.8.2 Question Metadata

```text
question_template_id
curriculum_version
topic_id
skill_id
grade_band
difficulty_label
difficulty_confidence
question_type = multiple_choice
parameter_schema
generation_constraints
solution_function
correct_option_generator
distractor_generators
common_error_tags
estimated_time_seconds
generator_model
review_model_versions
validation_status
active_status
version
created_at
```

Question variant:

```text
question_variant_id
question_template_id
random_seed
rendered_question
option_a
option_b
option_c
option_d
correct_option
parameter_values
generated_at
```

---

### 5.8.3 AI Generation Pipeline

```text
Curriculum Topic
  ↓
Question Generator Agent
  ↓
Structured Question Template
  ↓
Independent Solver Agent A
  ↓
Independent Solver Agent B
  ↓
Difficulty Reviewer Agent
  ↓
Ambiguity Reviewer Agent
  ↓
Curriculum Alignment Reviewer
  ↓
Deterministic/Executable Validation
  ↓
Deduplication
  ↓
Activate or Quarantine
```

Do not place free-form LLM-generated questions directly into production.

Use Bedrock Structured Outputs to enforce JSON Schema, then validate again with Pydantic.  
Source: [Amazon Bedrock Structured Outputs](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html)

---

### 5.8.4 Difficulty Assignment

Initial difficulty is determined from:

- Number of required operations
- Number of prerequisite skills
- Numerical magnitude
- Presence of fractions, negative numbers, or decimals
- Level of abstraction
- Similarity of distractors
- Expected time burden
- Likelihood of common misconceptions

Final initial label:

```text
Initial difficulty
= LLM ensemble classification
+ deterministic complexity features
+ independent solver agreement
```

As production data accumulates, recalibrate using:

- Actual accuracy
- Average response time
- Item discrimination
- Accuracy by grade
- Success after hints

The LLM label is only a bootstrap label.

---

### 5.8.5 Automated Validation

Every multiple-choice item must pass:

- Exactly one correct answer
- Unique answer options
- Correct option matches executable solution
- No division by zero
- Numeric values within allowed range
- Complete question wording
- No answer leakage
- No duplicate question
- Difficulty-rubric compliance
- Topic and skill alignment
- Age-appropriate wording

Use Python, SymPy, or custom evaluators.

---

### 5.8.6 Random Selection

At runtime:

```sql
WHERE topic_id = ?
AND difficulty = ?
AND active_status = 'active'
ORDER BY random()
LIMIT 2
```

Do not repeat a template within the same assessment.

Historical exposure does not permanently exclude a template; generate a new numerical variant instead.

---

### 5.8.7 Problem Reports and Quarantine

Students can report:

- No correct answer
- More than one correct answer
- Unclear wording
- Incorrect difficulty
- Display issue
- Other

Multiple reports from the same user count once.

After reports from five distinct valid users:

```text
active_status = quarantined
```

Result:

- Stop future delivery immediately
- Preserve prior attempts
- Do not hard-delete
- Add to evaluation queue
- Create a new version if corrected
- Preserve old version for audit

---

## 5.9 Pre-Exam

### 5.9.1 Assessment Composition

For each topic:

```text
Difficulty 1: 2 questions
Difficulty 2: 2 questions
Difficulty 3: 2 questions
Difficulty 4: 2 questions
Difficulty 5: 2 questions
Total: 10 questions
```

The Topic Resolver maps free-text student input to internal curriculum IDs.

---

### 5.9.2 Fixed Assessment Set

Once created, the question set is fixed:

```text
assessment_session
assessment_items
question_variant_id
display_order
```

Refreshes and retries do not generate a new set.

Use an idempotency key:

```text
POST /learning/sessions/{session_id}/answers
Idempotency-Key: ...
```

---

### 5.9.3 Multiple-Choice Grading

No LLM is used:

```text
selected_option == correct_option
```

Store:

```text
student_external_id
assessment_session_id
question_variant_id
selected_option
correct_option
is_correct
response_time_ms
submitted_at
```

---

## 5.10 Student Level and Mastery Estimation

### 5.10.1 Bootstrap Model

Use:

- Raw accuracy
- Difficulty-weighted accuracy
- Accuracy by difficulty
- Accuracy by skill
- Response time
- Highest consistently successful difficulty
- Grade-based prior

Example:

```text
Weighted Score =
Σ(correct × difficulty_weight)
/
Σ(difficulty_weight)
```

Example weights:

```text
Level 1 = 1.0
Level 2 = 1.4
Level 3 = 1.9
Level 4 = 2.5
Level 5 = 3.2
```

---

### 5.10.2 Enterprise Mastery Model

After enough response data is collected, adopt Item Response Theory or Bayesian mastery estimation:

```text
P(correct | student ability, item difficulty)
```

Store:

```text
estimated_theta
theta_confidence_interval
mastery_probability_by_skill
recommended_difficulty
model_version
```

Do not treat ten questions as an absolute measure of ability. The UI should say `Current estimated level`.

---

### 5.10.3 Skills to Strengthen

Use:

- Pre-exam errors
- Repeated study errors
- Hint usage
- Solution exposure
- Post-exam errors
- Response time
- Recent semantic memory

Example skill identifiers:

```text
fraction_common_denominator
negative_sign_handling
distributive_property
linear_equation_inverse_operation
quadratic_factoring
```

Student-facing language should use:

- Skills to strengthen
- Your next growth area
- Recommended practice
- Almost there

Tutor-facing summaries may use exact internal skill IDs.

---

## 5.11 Personalized Study and Human-in-the-Loop

### 5.11.1 Base Study Plan

Each topic includes five base study questions:

```text
StudyPlan
- topic_id
- target_skill_ids
- starting_difficulty
- base_problem_count = 5
- maximum_attempts_per_skill
- intervention_policy
```

Additional remediation questions are tracked separately.

---

### 5.11.2 Question Selection Priority

**Amended 2026-08-20 (D-325).** **Rule 4 outranks rules 2 and 3 in the implementation**, deliberately
and for a measured reason: on the dev database **57 of 201 study items (28%) repeated one of their own
session's exam templates, 40 of them at the very first study item**. `study_plan.py` states it inline
— one tier off is a worse *question*, but the same question is a worse *measurement*, so the
difficulty preference yields to "not yet used in this session", which D-325 widened to include the
session's exam. Rules 1, 5, 6 and 7 are unchanged, and rules 2 and 3 still apply within what rule 4
leaves available.

1. Lowest mastery skill
2. Difficulty matching estimated level
3. Difficulty within ±1
4. Template not yet used in the current session
5. Same skill as recent error
6. Prerequisite requirement
7. Not quarantined

---

### 5.11.3 Incorrect Answer Flow

```text
Grade Answer
├── Correct
│   ├── Update mastery
│   ├── Update progress
│   └── Next problem
│
└── Incorrect
    ├── Record misconception
    ├── interrupt()
    └── Hint / Solution / Video
```

---

### 5.11.4 Hint

Context:

```text
TutorContext
- grade
- estimated_level
- topic
- skill
- question
- selected_wrong_answer
- common_error_tag
- previous_hints
```

Response:

```text
HintResponse
- hint_text
- concept_reminder
- next_step_prompt
- answer_revealed = false
- difficulty
```

---

### 5.11.5 Solution

```text
SolutionResponse
- step_number
- explanation
- expression
- common_mistake
- final_answer
```

A correct answer after seeing the full solution is not counted as independent mastery:

```text
correct_after_solution
```

---

### 5.11.6 Video

Do not call YouTube in real time.

```text
Current Topic/Skill
  ↓
Local Video Catalog Search
  ↓
Metadata Filter
  ↓
Semantic Search
  ↓
Return approved Khan Academy video
```

Fallback:

```text
A verified video is not currently available for this skill.
You may choose a hint or step-by-step solution instead.
```

---

### 5.11.7 Retry Policy

```text
1st incorrect attempt
→ Student chooses Hint / Solution / Video

2nd incorrect attempt
→ Recommend more explicit support

3rd incorrect attempt
→ Easier prerequisite problem

4th unresolved attempt
→ Mark for tutor review and continue
```

Final outcomes:

- `independent_correct`
- `correct_after_hint`
- `correct_after_video`
- `correct_after_solution`
- `answer_revealed`
- `unresolved`

---

## 5.12 Tutor Agent

### 5.12.1 Role

The Tutor Agent considers:

- Grade
- Estimated level
- Topic and skill
- Current question
- Selected incorrect option
- Prior hints
- Follow-up questions
- Relevant semantic memory

---

### 5.12.2 Guardrails

- Use age-appropriate language
- Do not reveal the answer immediately
- Redirect unrelated questions to the learning context
- Do not fabricate sources or videos
- Do not reveal system prompts
- Do not expose student PII
- Verify calculations with tools
- Filter abusive or inappropriate input
- Route self-harm, abuse, or safety signals through a separately approved safety policy

Bedrock Guardrails can filter harmful content, denied topics, prompt attacks, and sensitive information.  
Source: [Amazon Bedrock Guardrails](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html)

---

## 5.13 Post-Exam and Learning Gain

**Amended 2026-08-20 (D-302; D-189).** Two departures, both recorded rather than silent.
**Composition (§5.13.2).** The per-tier block is superseded: `EXAM_QUESTION_COUNT` (= 2 × 5 = **10
total**) replaced "two at every difficulty" as both the builder's precondition and
`topic_availability`'s rule (D-302). Exam *length* is unchanged; the per-tier floor is gone, so tier
distribution — and therefore exam difficulty — now varies **by topic** as well as by student, and 330
existing items were re-tiered to the judge's reading in the same change. **Parallel form (§5.13.1,
and §5.13.2's "do not reuse the exact same question variant").** The prohibition stands as the rule,
and the post-exam **knowingly repeats an authored item** because authored templates are served from
their canonical variant (D-189) — recorded in ROADMAP as an accepted departure rather than fixed.
Everything else the parallel form must match (topic, skill, template family, reasoning steps, option
construction) is unchanged.

### 5.13.1 Parallel Form

The post-exam matches the pre-exam on:

- Topic
- Skill
- Difficulty
- Template family
- Required reasoning steps
- Multiple-choice option construction

It differs in:

- Numerical parameters
- Option order
- Random seed

Example:

```text
Pre:
2x + 3 = 11

Post:
3x + 4 = 19
```

---

### 5.13.2 Post-Exam Composition

Per topic:

```text
Difficulty 1: 2
Difficulty 2: 2
Difficulty 3: 2
Difficulty 4: 2
Difficulty 5: 2
```

Do not reuse the exact same question variant.

---

### 5.13.3 Learning-Gain Metrics

Store:

- Pre raw score
- Post raw score
- Raw gain
- Weighted gain
- Normalized gain
- Skill-level gain
- Difficulty transition
- Independent-correct rate
- Hint dependency
- Solution dependency
- Unresolved skill
- Change in average response time

```text
Raw Gain = Post Score - Pre Score
```

```text
Normalized Gain =
(Post - Pre) / (Maximum - Pre)
```

When the pre-exam score is already perfect:

```text
normalized_gain_status = not_applicable_pre_max
```

---

## 5.14 Real-Time Progress UI

### 5.14.1 Transport

Use Server-Sent Events:

```text
FastAPI
→ LangGraph stream events
→ SSE endpoint
→ Browser progress UI
```

SSE is appropriate because:

- The main flow is server-to-browser
- It uses standard HTTP
- It supports automatic reconnection
- It is simpler operationally than WebSockets
- It works well for token and graph-event streaming

Add WebSockets only if future use cases require bidirectional real-time collaboration.

---

### 5.14.2 Student View

Display:

- Current phase
- Completed questions
- Topic progress
- Current difficulty
- Correct-answer streak
- Remaining base questions
- Additional practice questions
- Hint count
- Solution count
- Video count
- Current estimated level
- Pre/post change
- Mastery change
- Skills to strengthen
- Learning streak

Use growth-oriented wording.

Example:

```text
You completed 7 of 10 questions.
Your accuracy improved on fraction comparison.
One more skill to strengthen: finding common denominators.
```

---

### 5.14.3 Parent Dashboard

Parents can view:

- All learning sessions
- Attendance-verification result
- Selected topics
- Pre-exam score
- Study results
- Post-exam score
- Learning gain
- Skill mastery
- Hint, solution, and video usage
- Tutor-review flag
- Weekly automated report
- Progress trend
- Problem reports
- Completion status

The dashboard is hosted on `learning.intellichoice.org`.

---

### 5.14.4 Tutor and Branch Manager Views

Tutors and branch managers do not access `learning.intellichoice.org`.

Instead, `go.intellichoice.org` calls the Learning API server-to-server and displays only:

- Pre/post scores
- Learning gain
- Skills to strengthen
- Tutor-review requirement
- Recommended on-site learning focus

Do not expose:

- Full chat transcripts
- Parent reports
- Location
- Solution images
- Unnecessary student free text

---

## 5.15 Procedural, Episodic, and Semantic Memory

### 5.15.1 Procedural Memory

Procedural memory defines system behavior:

- Hint sequence
- Solution-release conditions
- Question-selection policy
- Tutor-response policy
- Attendance-blocking policy
- Email-approval policy
- Memory-distillation rules
- Tool permissions
- Safety rules

Storage:

```text
Git Repository
├── prompts/
├── policies/
├── graph_config/
└── memory_procedures/
```

Version:

```text
procedure_name
procedure_version
effective_from
model_compatibility
evaluation_baseline
```

Procedural memory is not modified per student.

---

### 5.15.2 Episodic Memory

**Amended 2026-08-20 (D-333).** The retention windows below are **governed by D-333**, which is the
decision of record: completed learning checkpoints **30 days** (this section's own number),
abandoned/pending learning checkpoints **90 days of inactivity**, and **chat checkpoints 180 days of
inactivity** — a clock this section has **no row for**. Deletion is gated on long-term memory
consolidation succeeding first, and a successful no-op counts as success; a checkpoint whose
consolidation fails is retained and retried. Chat-api persists nothing else about a conversation, so
its checkpoint is the only record of what a visitor was told, which is why the chat window is the
longest of the three. The remaining rows and "final retention requires legal and policy approval"
are unchanged.

Episodic memory records actual learning events:

- Question attempted
- Selected answer
- Hint provided
- Video selected
- Retry count
- Follow-up question
- Post-exam improvement

```text
learning_events
- event_id
- student_external_id
- session_id
- event_type
- topic_id
- skill_id
- question_id
- structured_payload
- occurred_at
```

Do not retain raw conversation indefinitely.

Recommended initial retention:

- Raw chat messages: 90 days
- Structured learning events: enrollment period plus policy-defined retention
- Completed checkpoints: 30 days
- Pending interrupted sessions: up to 90 days
- Security/audit logs: one year
- Solution images: delete immediately after analysis

Final retention requires legal and policy approval.

---

### 5.15.3 Semantic Memory

Semantic memory contains durable structured learning facts.

Examples:

```text
- Struggles with negative signs when distributing
- Solves one-step equations independently
- Often needs a hint for common denominators
- Improved from difficulty 2 to difficulty 3 in linear equations
- Responds well to visual examples
```

Schema:

```text
semantic_memory_id
student_external_id
fact_type
topic_id
skill_id
fact_text
structured_value
confidence
evidence_event_ids
first_observed_at
last_confirmed_at
expires_at
memory_version
status
```

Do not infer personality, medical, or psychological traits.

---

### 5.15.4 Sunday Memory Consolidation

Run every Sunday:

```text
EventBridge Scheduler
  ↓
SQS
  ↓
Memory Consolidation Worker
  ↓
Load weekly episodic events
  ↓
PII minimization
  ↓
Summarizer Agent
  ↓
Structured semantic facts
  ↓
Deterministic validation
  ↓
Upsert semantic memory
```

Inputs:

- Previous week’s structured events
- Existing semantic facts
- Mastery changes
- Pre/post results

Output:

```text
MemoryUpdate
- facts_to_add
- facts_to_update
- facts_to_expire
- supporting_event_ids
- confidence
```

Do not store unsupported facts.

---

## 5.16 PostgreSQL Checkpointing

Use LangGraph PostgresSaver for resumable execution.

```text
LangGraph execution
  ↓
PostgresSaver
  ↓
thread_id + checkpoint_id
```

Use cases:

- Parent exits during child selection
- Student exits before selecting hint, solution, or video
- Email approval is pending
- Calendar approval is pending
- Temporary Bedrock error
- Server deployment
- Pod restart

Checkpoints are not the official learning record.

- Official record: Domain tables
- Execution resume state: Checkpoint tables

Source: [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)

---

## 5.17 Multimodal Solution Images

**Deferred 2026-08-20 (D-078; `IMAGE-WORK-PARK`) — the requirement is unchanged, not weakened.**
This is a **deferral marker, not an amendment**: every requirement below stands exactly as written
and **binds any future implementation from line one**. What is recorded is that **no code path
implements it today**. The user declined S29 before implementation, so no `BlobStore`, no
`MalwareScanner`, no `BedrockGateway.analyze_image`, no upload router, no executable math validator
and no `"image"` intervention choice exists anywhere in the codebase. Two preconditions gate any
future build, per D-078: (1) a minor's solution photo can incidentally capture a face, other
homework or a home background — a privacy question §5.1.4's consent language and §5.17.2's storage
policy assume away rather than resolve, including whether a parent-level opt-in is needed; and
(2) every supporting dependency (a real malware scanner, real S3 encryption at rest) is still on
D-002's no-real-credentials footing.

### 5.17.1 Processing Flow

```text
Student uploads image
  ↓
File type and size validation
  ↓
Malware scan
  ↓
Ephemeral encrypted storage
  ↓
Bedrock VLM analysis
  ↓
Extract equations and steps
  ↓
Pydantic validation
  ↓
Executable math validation
  ↓
Return feedback
  ↓
Immediately delete image
```

---

### 5.17.2 Storage Policy

- Do not store in the long-term RAG bucket.
- Do not store in versioned long-term S3.
- Do not include in backups.
- Do not include the image or Base64 in LangSmith traces.
- Minimize filename and metadata logging.
- Delete after success or failure.
- Retain only necessary extracted equations and error steps.

Implementation options:

1. Encrypted ephemeral pod volume
2. Dedicated non-versioned temporary S3 bucket
3. Deletion worker plus short lifecycle rule

The lifecycle rule is a final safeguard, not the primary deletion mechanism.

---

### 5.17.3 Grading

The current assessment is multiple-choice, so images do not determine the final score.

Image analysis supports:

- Identifying the incorrect step
- Generating better hints
- Extracting misconception tags

The selected multiple-choice option determines the score.

---

## 5.18 Weekly YouTube Synchronization

### 5.18.1 External Sync

Synchronize Khan Academy’s official YouTube metadata once per week:

```text
EventBridge Scheduler
  ↓
YouTube Sync Worker
  ↓
YouTube Data API
  ↓
Uploaded videos / playlists
  ↓
Metadata normalization
  ↓
Topic classification
  ↓
Embedding
  ↓
PostgreSQL + pgvector
```

The YouTube Data API can retrieve uploaded videos through the channel’s uploads playlist and `playlistItems.list`.  
Source: [YouTube Data API — playlistItems](https://developers.google.com/youtube/v3/docs/playlistItems)

---

### 5.18.2 Stored Metadata

```text
youtube_video_id
channel_id
channel_title
video_url
title
description
playlist_ids
duration
published_at
thumbnail_url
language
topic_ids
skill_ids
grade_band
difficulty_min
difficulty_max
embedding
last_synced_at
active_status
```

Do not store:

- Video files
- Unauthorized copied transcripts
- Full comments
- User viewing history
- YouTube account data

Mark deleted or private videos as inactive.

---

### 5.18.3 Learning-Time Search

Do not call the YouTube API during learning.

```text
Video option
  ↓
youtube_catalog.search MCP Tool
  ↓
PostgreSQL metadata filter
  ↓
pgvector semantic search
  ↓
Approved result
```

Use a standard worker/API for external synchronization and expose the local catalog to LangGraph through an internal MCP tool.

---

## 5.19 Organization Q&A LangGraph

### 5.19.1 Access Scope

#### Anonymous

- Public FAQ
- Public branch information
- Nearest-branch search
- Public academic calendar
- Volunteer information
- Student-participation information
- `.ics` generation
- Admin contact

#### Authenticated Student or Parent

- Anonymous functions
- Parent and student handbooks
- Role-appropriate schedules
- Branch-specific restricted documents
- Role-appropriate guidance

#### Tutor

- Tutor handbook
- Tutor procedures
- Tutor-specific branch information
- Role guidance

#### Branch Manager

- Branch Manager Manual
- Branch operations
- Schedules and policies
- Internal escalation procedures

When a user requests higher-access content, require authentication.

---

### 5.19.2 Workflow

```text
START
  ↓
Detect authentication
  ↓
Resolve role
  ↓
Scope Guard
  ├── Out of scope → Refusal
  └── In scope
       ↓
Intent Router
       ├── Document QA → RAG
       ├── Branch Locator → Google Maps MCP
       ├── Calendar → Calendar Agent
       ├── Admin Contact → Gmail MCP
       └── Insufficient information → Clarification
  ↓
Response Verifier
  ↓
END
```

---

### 5.19.3 Q&A State

**Amended 2026-08-20 (`AMENDMENT-SWEEP`).** `ephemeral_location` in the list below **does not exist**
on `QAState`, and the branch-locator fields are still absent — `apps/chat-api/src/chat_api/graph/
state.py` says so in its own module docstring. The code is right; this list and a stale in-code
comment are the drift. The location-consent *requirement* (§5.1.3) is unaffected — this marker is
about the state shape, not the consent rule.

```text
QAState
- session_id
- user_external_id
- authenticated
- user_role
- branch_external_id
- query
- standalone_query
- scope
- intent
- role_access_filter
- retrieved_chunks
- citation_candidates
- answer
- groundedness_score
- location_consent
- ephemeral_location
- calendar_event
- email_draft
- pending_interrupt
- trace_id
```

---

### 5.19.4 Out-of-Scope Response

Supported topics:

- IntelliChoice organization
- Branches
- Volunteering
- Student participation
- Parent information
- Tutor procedures
- Academic calendar
- Learning application support

Response:

```text
I can help with IntelliChoice programs, branches, schedules, volunteering,
student learning, parent information and tutor or branch procedures.
I can't help with that topic through this assistant. For anything else, your branch
can point you to the right person.
```

**Amended 2026-08-15 (D-351).** The final line was *"I cannot answer unrelated general-purpose
questions."* Measured live: a parent asking how to request a refund for a donation made by
mistake was told their question was an unrelated general-purpose one. The classification is
correct — donations are not on the supported-topic list above, and D-351 deliberately did not
add them — but the sentence describes the *asker's question* using the classifier's own label.
The replacement keeps the actionable half and names a next step. The topic list is unchanged.

### 5.19.5 Turn reason codes

**Recorded 2026-08-20 (`AMENDMENT-SWEEP`) — a fact, not a decision.** Two divergences, neither
changing a requirement. The table below lists **nine** reasons; `TurnReason` in
`apps/chat-api/src/chat_api/services/outcomes.py` defines **ten** — `cancelled` has no row here. And
the reason is a **client-visible contract with an untyped client**: `apps/chat-web/src/types.ts:67`
declares `reason?: string | null` rather than narrowing to the union, so a client cannot fail to
compile on a reason it does not handle — the exact inference this section exists to prevent, moved
one layer out. The two rules that close this section are unchanged and still binding.

Every turn carries a machine-readable reason alongside its prose (D-351). The reason is the
contract; the wording is not. A client must branch on the reason rather than infer the cause
from `escalation_recommended`, `citations` and `access_hint` — that inference is how one
message came to serve three different causes (AUD-C-19).

| Reason | Meaning | Next step offered |
|---|---|---|
| `answer` | A grounded, citation-supported answer, or a deterministic success (calendar file, event listing, branch list) | — |
| `no_approved_source` | Supported topic; the approved corpus does not answer it | Escalate to a branch manager |
| `sources_conflict` | Approved sources disagree, so answering means choosing one | Escalate for confirmation |
| `access_required` | Matching content exists behind a role the caller does not hold | Sign in |
| `out_of_scope` | Not a topic this assistant covers (§5.19.4) | Ask the branch |
| `human_action_required` | The turn resolved through a person's decision — an email sent, declined or failed | — |
| `policy_restricted` | Refused by policy rather than knowledge: a rate limit, a declined consent | Retry later |
| `system_error` | A failure on our side. Explicitly **not** a statement about the question (§5.29) | Retry |
| `needs_clarification` | The assistant needs more from the caller — a ZIP code, which event | Supply it |

Two rules bind this table:

1. **No user-facing message may restate its own reason code.** An internal category is not a
   sentence to read at a visitor.
2. **`access_required` names no role and no document.** The response carries only the generic
   message; the matching tier is selected server-side and logged, never returned. Naming it
   tells an unauthenticated caller that a document restricted to that tier exists and mentions
   their terms — a disclosure produced by a probe that runs *because* the pipeline already
   declined, and one measured wrong in the field (AUD-C-25/D-179). Reversing this requires an
   explicit decision, not an edit.

---

## 5.20 RAG Documents and Storage

### 5.20.1 Initial Placeholder Documents

Because production documents are not yet available, create synthetic development and staging documents.

Every placeholder must include:

```text
DRAFT — NOT APPROVED FOR PRODUCTION
Synthetic content for development and evaluation only.
```

The production retriever searches only `status=approved`.

---

### 5.20.2 Content Repository

```text
knowledge-content/
├── manifests/
│   ├── public.yaml
│   ├── parent.yaml
│   ├── student.yaml
│   ├── tutor.yaml
│   └── branch_manager.yaml
│
├── documents/
│   ├── public/
│   │   ├── organization-overview/
│   │   ├── branch-directory/
│   │   ├── volunteer-guide/
│   │   ├── student-participation-guide/
│   │   ├── enrollment-faq/
│   │   ├── academic-calendar/
│   │   ├── privacy-notice/
│   │   ├── ai-use-notice/
│   │   └── contact-guide/
│   │
│   ├── parent/
│   │   ├── parent-handbook/
│   │   ├── attendance-policy/
│   │   └── learning-report-guide/
│   │
│   ├── student/
│   │   ├── student-handbook/
│   │   ├── code-of-conduct/
│   │   └── learning-platform-guide/
│   │
│   ├── tutor/
│   │   ├── tutor-handbook/
│   │   ├── instructional-procedures/
│   │   └── student-support-guide/
│   │
│   └── branch_manager/
│       ├── operations-manual/
│       ├── attendance-procedure/
│       ├── escalation-procedure/
│       └── branch-calendar/
│
└── schemas/
    ├── document_manifest.schema.json
    └── metadata.schema.json
```

---

### 5.20.3 S3 Layout

```text
s3://intellichoice-kb-{environment}/
├── incoming/
├── approved/
│   ├── public/
│   ├── parent/
│   ├── student/
│   ├── tutor/
│   └── branch_manager/
├── processed/
├── rejected/
└── manifests/
```

Environments:

```text
intellichoice-kb-dev
intellichoice-kb-staging
intellichoice-kb-prod
```

Enable S3 versioning and SSE-KMS.

Document approval occurs through GitHub pull requests and CI rather than a separate admin portal:

```text
Document change
→ Pull Request
→ Schema validation
→ Content review
→ Merge
→ Upload to approved S3 path
→ Ingestion
```

---

### 5.20.4 Document Versioning

Use annual versions:

```text
academic_year = 2026-2027
effective_from
effective_to
version
status
supersedes_document_id
```

Default retrieval uses only the currently effective approved version.

---

## 5.21 LlamaIndex RAG Pipeline

### 5.21.1 Ingestion

```text
S3 approved document
  ↓
Parser
  ↓
Layout and heading detection
  ↓
Chunking
  ↓
Metadata extraction
  ↓
Embedding
  ↓
PostgreSQL + pgvector
```

LlamaIndex ingestion pipelines support parsing, chunking, metadata extraction, and embedding transformations.  
Source: [LlamaIndex Data Loading and Ingestion](https://developers.llamaindex.ai/python/framework/understanding/rag/loading/)

---

### 5.21.2 Chunking

Use structural chunking, not only fixed character counts.

Boundaries include:

- Document title
- Heading
- Subheading
- Paragraph
- List
- Table
- Page
- Branch section
- Role-specific section

Schema:

```text
chunk_id
document_id
parent_chunk_id
chunk_text
document_title
page_number
section_title
branch_external_id
audience
access_level
academic_year
effective_from
effective_to
status
source_sha256
embedding
search_vector
```

Preserve table structure as Markdown or JSON.

---

### 5.21.3 Metadata Filtering

Apply before retrieval:

```text
status = approved
effective_from <= today
effective_to >= today
audience includes user_role
branch_id is null OR branch_id = current_branch
academic_year = requested_year
```

Do not retrieve unauthorized chunks and attempt to hide them later.

LlamaIndex PostgreSQL vector-store integrations support metadata storage and metadata filtering during retrieval.  
Source: [LlamaIndex PostgreSQL Vector Store](https://developers.llamaindex.ai/python/framework/integrations/vector_stores/postgres/)

---

### 5.21.4 Semantic Search

Use `pgvector` with:

```text
HNSW
vector_cosine_ops
```

Example:

```text
Question:
"When are classes not held?"

Document:
"Instruction is suspended during the Thanksgiving holiday."
```

---

### 5.21.5 Keyword Search

Use PostgreSQL full-text search:

```text
tsvector
GIN index
websearch_to_tsquery
```

Especially useful for:

- Branch names
- Dates
- Academic years
- Policy titles
- Email addresses
- Program names

---

### 5.21.6 Hybrid Search

```text
Query
├── PostgreSQL full-text search
└── pgvector semantic search
        ↓
Reciprocal Rank Fusion
        ↓
Top candidate chunks
```

AWS also supports hybrid search with Aurora PostgreSQL in Bedrock Knowledge Bases.  
Source: [AWS Hybrid Search Announcement](https://aws.amazon.com/about-aws/whats-new/2025/04/amazon-bedrock-knowledge-bases-hybrid-search-aurora-postgresql-mongo-db-atlas-vector-stores/)

---

### 5.21.7 Reranking

```text
Top 30 hybrid candidates
  ↓
Cross-encoder or Bedrock reranker
  ↓
Top 5–8 chunks
```

LlamaIndex supports node postprocessors for reranking and filtering after retrieval.  
Source: [LlamaIndex Node Postprocessors](https://developers.llamaindex.ai/python/framework/module_guides/querying/node_postprocessors/)

---

### 5.21.8 Citation Grounding

Response schema:

```text
GroundedAnswer
- answer
- citations
- confidence
- missing_information
- escalation_recommended
```

Citation schema:

```text
Citation
- document_title
- document_version
- page_number
- section_title
- source_reference
- supporting_quote_hash
```

Do not answer when:

- No approved source exists
- Retrieval score is below threshold
- Sources conflict
- Documents are expired
- User lacks access
- Individual approval is required
- Citations do not support the response

---

## 5.22 Branch Locator and Google Maps MCP

```text
Branch question
  ↓
Request location consent
  ↓
Browser location or ZIP input
  ↓
Read public branch coordinates
  ↓
Google Maps MCP
  ↓
Route duration and distance
  ↓
Sort branches
```

Tools:

```text
maps.geocode
maps.compute_routes
maps.find_nearest_branch
```

Apply application and API restrictions to Google Maps keys.  
Source: [Google Maps API Security Best Practices](https://developers.google.com/maps/api-security-best-practices)

Fallbacks:

- Location denied: ZIP or city input
- Maps unavailable: branch-address list
- Route unavailable: clearly labeled straight-line or ZIP-based estimate
- Never store precise location permanently

---

## 5.23 Calendar

### 5.23.1 Information Request

```text
"When is the next parent meeting?"
→ RAG answer only
```

### 5.23.2 Calendar Action

```text
"Add it to my calendar."
→ Calendar action
```

Schema:

```text
CalendarEvent
- title
- start_datetime
- end_datetime
- timezone
- location
- description
- source_document_id
- source_page
```

---

### 5.23.3 Google Calendar

```text
Event Preview
  ↓
interrupt()
  ↓
User Approval
  ↓
Google Calendar MCP
  ↓
Create Event
```

Google Calendar API requires appropriate OAuth scopes and consent.  
Source: [Google Calendar API Overview](https://developers.google.com/workspace/calendar/api/guides/overview)

Because Google Workspace is not assumed, use per-user OAuth rather than domain-wide delegation.

---

### 5.23.4 Apple Calendar and Anonymous Users

Generate `.ics` files compliant with RFC 5545.  
Source: [RFC 5545](https://datatracker.ietf.org/doc/html/rfc5545)

Validate:

- DTSTART
- DTEND
- Timezone
- UID
- DTSTAMP
- Escaping
- Line folding
- Duplicate event IDs

---

## 5.24 Gmail MCP

### 5.24.1 Email Paths

Attendance escalation:

```text
Sender: configured system Gmail account
Recipient: Branch Manager email from MySQL
```

Q&A escalation:

```text
Sender: configured system Gmail account
Recipient: configured Admin recipient
```

---

### 5.24.2 Approval Flow

```text
Generate draft
  ↓
Pydantic validation
  ↓
PII warning
  ↓
Show preview
  ↓
interrupt()
  ├── Edit
  ├── Cancel
  └── Approve
       ↓
       Gmail MCP send
```

Anonymous email protection:

- CAPTCHA
- IP and user rate limiting
- Maximum body length
- Attachment restriction
- Prompt-injection filtering
- Header-injection defense
- Abuse detection

---

### 5.24.3 Google Account Requirements

Because Google Workspace is not assumed:

- Organization-managed Google account
- Google Cloud project
- OAuth consent screen
- Gmail API enabled
- Minimum necessary OAuth scopes
- Encrypted refresh token storage
- OAuth redirect URIs
- Separate staging and production OAuth clients

Public applications using sensitive Google scopes may require OAuth app verification.  
Source: [Google OAuth Scopes](https://developers.google.com/identity/protocols/oauth2/scopes)

---

## 5.25 AWS Bedrock and Structured Responses

### 5.25.1 Bedrock Gateway

**Amended 2026-08-20 (`REQ-32-SAFETY`, UD-9; `AMENDMENT-SWEEP`).** Two entries in the benefits list
below are **declared and never used**: **Guardrails** — a repo-wide case-insensitive `guardrail`
grep across `packages`, `apps` and `scripts`, including `.tf`, `.yaml` and `.json`, returns **zero
hits** — and gateway-level **PII redaction**, which lives at callers rather than in the gateway. The
remainder are present and quotable in
`packages/adapters/src/intellichoice_adapters/bedrock/gateway.py`: `call_timeout_s=20.0`, the
bounded retry loop, `_HARD_MAX_OUTPUT_TOKENS=4000`, a pre-call `session_budget_cents=50.0`, the
circuit breaker and `worst_case_cost_cents`. Whether to adopt Bedrock Guardrails or amend this list
is an **open user decision (UD-9)** and is not decided by this marker; the requirement stands.

```python
class BedrockGateway:
    async def generate_structured(...)
    async def generate_stream(...)
    async def classify(...)
    async def create_embedding(...)
    async def analyze_image(...)
    async def judge(...)
```

Benefits:

- Model replacement
- Retry policy
- Timeouts
- Token accounting
- Guardrails
- PII redaction
- Model versioning
- Cost control
- Circuit breaking

---

### 5.25.2 Task-Specific Model Selection

| Task | Required Model Characteristics |
|---|---|
| Scope and intent | Fast and low-cost |
| Topic mapping | Reliable structured output |
| Tutor | Strong educational explanation |
| Question generation | Mathematics and structured output |
| Question review | Independent from generator |
| Parent report | Strong summarization |
| RAG answer | Grounding and long context |
| VLM | Image and formula understanding |
| LLM judge | Independent from production answer model |

---

### 5.25.3 Structured Responses

> **Amended 2026-08-20 (`BATCH-LOW-UNMARKED-SPEC`/DRIFT-55, W-43).** Eleven of the thirteen
> artifact types below have a Pydantic model and a non-mock production call site. Two are
> **declared and never used** — both dispositioned deterministic, so the gap is document-side,
> not a build gap: **Topic mapping** (`BedrockTask.TOPIC_MAPPING` exists with no payload model,
> no response model and no caller — D-024's topic resolver is deterministic) and **Email draft**
> (no LLM response model; both email-draft paths are server-composed and deterministic per
> D-020/§5.6.4). The list is retained as written; the two entries bind only a future LLM-backed
> implementation, if one is ever decided.

Use JSON Schema for:

- Intent
- Topic mapping
- Question template
- Hint
- Solution
- Tutor response
- Parent report
- Semantic-memory update
- Calendar event
- Email draft
- RAG answer
- Citation
- Evaluation result

```text
Bedrock Structured Output
  ↓
Pydantic Validation
  ├── Valid → Continue
  └── Invalid
       ↓
       Limited retry
       ↓
       Deterministic fallback
```

---

## 5.26 SQL, Structured Output, and Constrained Decoding

### 5.26.1 Production Runtime SQL

Do not generate SQL from ordinary user requests.

Use predefined repository methods:

```text
get_student_assessment_summary(student_id)
get_weak_skills(student_id, week_id)
get_active_questions(topic_id, difficulty)
search_document_chunks(filters, query)
get_parent_children(parent_id)
```

Implementation:

- SQLAlchemy
- Parameterized queries
- Pydantic inputs
- Transactions
- Row-level authorization
- Query timeouts

---

### 5.26.2 Role of Structured Output

Use structured output to choose an approved operation:

```text
Natural-language request
→ QueryIntent
→ Pydantic model
→ Approved repository function
```

Example:

```json
{
  "operation": "get_weekly_learning_summary",
  "student_id": "student_123",
  "week_id": "2026-W28"
}
```

The LLM does not produce raw SQL.

---

### 5.26.3 Internal NL2SQL

**Open — recorded 2026-08-20 (`DRIFT-66-NL2SQL`, UD-12(d)).** This is **not** an amendment: the
internal-tool requirement below is **unbuilt and undecided in both directions**. Nothing in ROADMAP
or DECISIONS says the internal dev/eval/analytics NL2SQL is planned, scoped, partially present or
dropped, and one line either way closes it (UD-12(d)). The requirement therefore still stands as
written and binds any future build, including all twelve controls. The **runtime** prohibition is
separate and holds: no runtime NL2SQL exists — every query path is a parameterized `select()` — and
§5.0 and §5.26.1 continue to forbid runtime NL2SQL regardless of what is decided here.

Use only for development, evaluation, and internal analytics.

```text
Developer query
  ↓
Structured Query Plan
  ↓
Allowed table/column validation
  ↓
SQL generation
  ↓
SQL parser
  ↓
Read-only database role
  ↓
EXPLAIN validation
  ↓
Statement timeout
  ↓
Row limit
  ↓
Execution
```

Controls:

- No production write access
- Read replica or sanitized dataset
- `SELECT` only
- Table allowlist
- Column allowlist
- PII-column prohibition
- Subquery-depth limit
- SQL parser such as SQLGlot
- Mandatory `LIMIT`
- Query-cost limit
- Full SQL audit log

Constrained decoding improves syntax reliability but does not enforce authorization or prevent data leakage.

---

## 5.27 Pydantic

Use Pydantic at every boundary:

- FastAPI request and response
- LangGraph state
- Tool arguments
- Bedrock structured output
- MCP results
- Calendar
- Email
- Question templates
- Memory updates
- Evaluation results

Example:

```python
class InterventionChoice(str, Enum):
    HINT = "hint"
    SOLUTION = "solution"
    VIDEO = "video"


class InterventionRequest(BaseModel):
    session_id: UUID
    question_id: UUID
    choice: InterventionChoice
```

Do not execute an invalid tool call.

---

## 5.28 FastAPI and Async

### 5.28.1 Learning API

```text
POST /learning/sessions
POST /learning/sessions/{id}/student
POST /learning/sessions/{id}/topics
POST /learning/sessions/{id}/answers
POST /learning/sessions/{id}/interventions
POST /learning/sessions/{id}/resume
GET  /learning/sessions/{id}/stream
GET  /learning/students/{id}/history
GET  /learning/students/{id}/reports
```

### 5.28.2 Chat API

```text
POST /chat/sessions
POST /chat/sessions/{id}/messages
GET  /chat/sessions/{id}/stream
POST /chat/sessions/{id}/location-consent
POST /chat/sessions/{id}/calendar-preview
POST /chat/sessions/{id}/calendar-create
POST /chat/sessions/{id}/email-preview
POST /chat/sessions/{id}/email-send
```

---

### 5.28.3 Async Workloads

Use async for:

- Parallel MySQL and PostgreSQL reads
- Bedrock calls
- MCP calls
- Hybrid search
- Reranking
- Branch route calculations
- SSE streaming
- Embeddings
- Weekly report generation

Use SQS workers for:

- PDF ingestion
- YouTube synchronization
- Memory consolidation
- Question generation
- Large-scale evaluation
- Re-indexing

---

## 5.29 Graceful Failure Handling

> **Amended 2026-08-20 by user sign-off (DRIFT-15/REQ-49).** Two mechanisms in this
> section's common-mechanism list were never built and are removed as requirements:
> no dead-letter queue exists (zero DLQ/SQS hits across packages, apps, scripts and
> terraform), and no smaller-model fallback exists — the Bedrock timeout path is
> bounded retry against the same `model_id`, then circuit-open, so degradation is
> deliberately binary. The built mechanisms (timeout, bounded retry, backoff,
> circuit breaker, idempotency, static concept-hint fallback, user-safe error
> messages) remain required. If future scale or operational needs justify a DLQ or
> a model-downgrade path, they are introduced by a new explicit decision.
>
> Coverage note: of the nineteen rows, four were sampled in the 2026-08
> reconciliation; the other fifteen are unverified — and unverified counts as not
> traced (TRACEABILITY method rule). This does not imply the unsampled rows are
> defective, only that their traceability status has not been established. The VLM
> row is deferred with the image feature (D-078), not parked and not weakened.

| Failure | Response |
|---|---|
| MySQL profile failure | Disable authenticated functions; keep public Q&A available |
| MySQL attendance failure | Block learning start |
| PostgreSQL writer failure | Stop answer submission and safely retry |
| Bedrock timeout | Bounded retry and smaller-model fallback |
| Structured-output failure | Pydantic repair and safe error |
| Hint generation failure | Verified static concept hint |
| YouTube sync failure | Keep last valid catalog |
| No video result | Offer hint or solution |
| Gmail MCP failure | Preserve draft |
| Maps MCP failure | Provide address or ZIP-based fallback |
| Google Calendar failure | Generate `.ics` |
| No RAG result | Do not guess; offer escalation |
| Conflicting RAG sources | Surface conflict and offer escalation |
| Checkpoint conflict | Optimistic lock and reload |
| VLM failure | Delete image and request text input |
| LangSmith failure | Continue user request |
| Prometheus failure | Continue product operation |

Common mechanisms:

- Timeout
- Bounded retry
- Exponential backoff
- Circuit breaker
- Idempotency
- Dead-letter queue
- Fallback
- User-safe error message

---

## 5.30 PII Handling and Security

### 5.30.1 Minimum Necessary Data

**Amended 2026-08-20 (`AMENDMENT-SWEEP`).** The two halves below hold differently, and both are
stated because only one is drift. The **denylist holds completely**: none of the seven forbidden
names appears in any of the 23 Bedrock payload models. The **allowlist does not describe the
surface**: the seven-field list matches exactly one of those 23 payloads, and the others carry other
fields. Two of those fields are recorded here as **facts, not decisions**, and are deliberately left
unresolved. (1) `StageNarrativePayload.attendance_status`
(`packages/shared/src/intellichoice_shared/bedrock.py`) crosses to the wire, which is in tension
with the MySQL-only framing of §5.4.1 and §5.30 — attendance is read from MySQL and its *status*
then travels in an LLM payload. (2) `RagAnswerPayload.user_role` survived D-219, which removed the
same field from `ScopeAndIntentPayload` precisely so an access decision would stop being made inside
a prompt — in tension with non-negotiable rule 3. Both are recorded per the register's
`AMENDMENT-SWEEP` entry; neither is resolved here, and no requirement below is weakened.

Send to Bedrock:

```text
grade
current_topic
skill
estimated_level
question
selected_answer
relevant_learning_fact
```

Do not send:

```text
full_name
email
phone
home_address
precise_location
parent_contact
branch_manager_email
```

---

### 5.30.2 Authorization Matrix

| Role | Access |
|---|---|
| Anonymous | Public Q&A |
| Student | Own learning |
| Parent | Linked children |
| Tutor | Tutor documents and summaries in go |
| Branch Manager | Manager documents and branch summaries in go |
| Admin | Approved administrative functions |

Enforce authorization in the backend and query layer, not in prompts.

---

### 5.30.3 AWS Security

- IAM Roles for Service Accounts
- Secrets Manager
- KMS
- S3 Block Public Access
- Private subnets
- VPC endpoints
- Security groups
- AWS WAF
- Rate limiting
- ECR image scanning
- CloudTrail
- GuardDuty
- RDS encryption
- TLS
- Pod Security Standards
- NetworkPolicy

---

### 5.30.4 Prompt Injection Defense

Treat RAG content as untrusted input.

- Do not treat document instructions as system instructions.
- Separate retrieved content from system policy.
- Do not execute tools solely because a document requests it.
- Enforce tool permissions in the backend.
- Apply URL allowlists.
- Sanitize email headers.
- Sanitize Markdown and HTML.

---

## 5.31 Evaluation

### 5.31.1 Deterministic Evaluators

- Attendance gating
- Parent-child authorization
- Number of questions per difficulty
- Multiple-choice grading
- Score calculation
- Learning-gain calculation
- Graph routing
- Email approval
- Calendar approval
- Citation presence
- Role metadata filtering
- Quarantine threshold
- Image deletion event

---

### 5.31.2 Executable Evaluators

- Mathematical answer
- Distractor uniqueness
- Equation solution
- Parameter constraints
- `.ics` syntax
- SQL parser validation
- Pydantic schema
- API contract
- Question variant generation

---

### 5.31.3 LLM-as-a-Judge

Adaptive Learning:

- Grade appropriateness
- Level appropriateness
- Whether hints avoid revealing the answer
- Solution accuracy and clarity
- Whether the response addresses the student’s error
- Growth-oriented tone

Q&A:

- Faithfulness to sources
- Citation support
- No unsupported guessing
- Role appropriateness
- Appropriate refusal

Use a judge model different from the production answer model when possible.

---

### 5.31.4 Golden Dataset

Learning:

- Grade-to-topic mapping
- Difficulty-specific questions
- Common errors
- Hints
- Solutions
- Video routing
- Attendance branches
- Parent-child authorization
- Pre/post parallel forms
- Memory consolidation

Q&A:

- Public FAQ
- Role-specific FAQ
- Branch questions
- Academic calendar
- Conflicting sources
- No-answer cases
- Maps tool
- Calendar tool
- Gmail escalation
- Out-of-scope requests
- Prompt injection

---

### 5.31.5 Regression Testing

```text
Code or prompt change
  ↓
Unit tests
  ↓
Graph route tests
  ↓
Tool contract tests
  ↓
Golden dataset
  ↓
RAG evaluation
  ↓
LLM judge
  ↓
Latency/cost comparison
  ↓
Release gate
```

Block deployment if quality falls below the defined threshold.

---

## 5.32 Observability

### 5.32.1 LangSmith Selection

**Amended 2026-08-20 (D-214, D-242).** The "choose one after contractual review" fork at the end of
this section is **decided**: LangSmith **Cloud with complete PII masking**, not self-hosted
LangSmith Enterprise. Masking is asserted as *not optional* in its own test (D-242), and reachability
is provided by a single deliberately one-AZ NAT gateway driven by the tracing flag, so it cannot be
left billing when tracing is off (D-214). The rest of this section — LangSmith over LangFuse, and the
reasons — is unchanged.

Use LangSmith and do not use LangFuse in the initial architecture.

Reasons:

- Direct LangGraph tracing
- Dataset evaluation
- Offline and online evaluation
- Prompt and experiment comparison
- OpenTelemetry integration
- Enterprise self-hosting option

Source: [LangSmith Evaluation](https://docs.langchain.com/langsmith/evaluation)

For minor-data protection, choose one after contractual review:

- Self-hosted LangSmith Enterprise
- LangSmith Cloud with complete PII masking

Source: [LangSmith Input and Output Masking](https://docs.langchain.com/langsmith/mask-inputs-outputs)

---

### 5.32.2 OpenTelemetry

```text
Browser request
→ FastAPI span
→ LangGraph span
→ Bedrock span
→ MySQL span
→ PostgreSQL span
→ MCP span
→ External API span
```

Use one `trace_id`.

---

### 5.32.3 Logging

```json
{
  "event": "learning_answer_submitted",
  "student_id_hash": "hashed-id",
  "session_id": "session-id",
  "question_id": "question-id",
  "is_correct": false,
  "latency_ms": 251,
  "trace_id": "trace-id"
}
```

Do not log:

- Student name
- Email
- Precise location
- Images
- Entire prompts
- Entire chat transcripts
- OAuth tokens

---

### 5.32.4 Prometheus and Grafana

Learning KPIs:

- Session starts
- Attendance-block rate
- Completion rate
- Pre/post completion
- Learning gain
- Hint, solution, and video usage
- Retry count
- Tutor flag
- Problem reports
- Quarantine count
- Cost per session

Q&A KPIs:

- RAG answer rate
- No-answer rate
- Citation coverage
- Email escalation
- Maps success
- Calendar success
- Out-of-scope refusal
- Cost per conversation

Infrastructure:

- Request rate
- Error rate
- P50/P95/P99 latency
- CPU
- Memory
- Pod count
- Queue depth
- DB connections
- Bedrock throttling
- MCP failures
- SSE connections

---

## 5.33 AWS Environments and Deployment

**Amended 2026-08-20 (D-004; confirmed at S32 by D-084).** The **substrate** prescribed in §5.33.1
–§5.33.3 was decided otherwise: no AWS Organizations three-account split, no EKS (and so no
Karpenter, HPA, PDB, NetworkPolicy, IRSA, namespaces or Helm releases), no Aurora. The build runs on
**ECS Fargate + RDS PostgreSQL with pgvector**, with a separately seeded RDS MySQL standing in for
`go.intellichoice.org`'s shape. A grep across `terraform` for
`aws_eks|kubernetes|aurora|karpenter|aws_organizations` returns **zero resources** — only comments
recording the rejection. What §5.33 requires and D-004 explicitly kept still binds: environment
separation (VPC/prefix-level before account-level), secrets in Secrets Manager, TLS, WAF,
Terraform-managed infrastructure, no PII replication, and never using production data in
development. Containers keep EKS available as a later migration, so the topology text below is a
retained option, not a deleted one.

### 5.33.1 Environment Isolation

```text
AWS Organization
├── Development Account
├── Staging Account
└── Production Account
```

Each environment has separate:

- VPC
- EKS
- Aurora PostgreSQL
- S3
- Secrets
- KMS keys
- OAuth credentials
- Bedrock configuration
- Domain configuration

Never use production data in development.

---

### 5.33.2 EKS

Production EKS:

- Three Availability Zones
- Managed node groups
- Karpenter or Cluster Autoscaler
- Horizontal Pod Autoscaler
- Pod Disruption Budget
- Rolling deployment
- Readiness and liveness probes
- NetworkPolicy
- IRSA
- Separate namespaces
- Separate Helm releases

Learning and Chat may share one production EKS cluster initially, while remaining isolated by namespace and release.

---

### 5.33.3 PostgreSQL

Recommended:

- Aurora PostgreSQL
- Multi-AZ
- One writer
- At least one reader
- Automated backups
- Point-in-time recovery
- Encryption
- pgvector
- Connection pooling
- Slow-query monitoring

Logical databases or schemas:

```text
learning
rag
memory
checkpoint_learning
checkpoint_chat
evaluation
```

---

### 5.33.4 Scaling Targets

**Amended 2026-08-20 (D-004; `AMENDMENT-SWEEP`).** The SLO and capacity targets below are
unchanged and still bind. The *mechanisms* below them describe the EKS/SQS substrate D-004
declined: the deployed footprint scales through Application Auto Scaling with **exactly one live
signal per service** — an ALB `TargetResponseTime` p95 StepScaling pair, or CPU target-tracking,
never both (`enable_latency_step_scaling` makes them mutually exclusive in
`terraform/modules/ecs-service/main.tf`) — and carries **zero SQS resources**, so the five HPA
signals and the queue-depth/oldest-message worker rules have no subject.

Targets:

- More than 1,000 students
- More than 100 concurrent learning sessions
- 99.9% monthly availability
- General API P95 near one second
- LLM time-to-first-token near three seconds

HPA signals:

- CPU
- Memory
- Active requests
- SSE connections
- P95 latency

Worker scaling:

- SQS queue depth
- Oldest-message age
- Processing time

---

## 5.34 Docker, Terraform, and GitHub Actions

### 5.34.1 Docker Images

```text
learning-api
learning-worker
chat-api
rag-worker
mcp-gateway
evaluation-runner
```

Each image must use:

- Non-root user
- Minimal base image
- Locked dependencies
- Health checks
- SBOM
- Vulnerability scanning
- No embedded secrets

---

### 5.34.2 Terraform

```text
terraform/
├── modules/
│   ├── vpc/
│   ├── eks/
│   ├── aurora/
│   ├── s3/
│   ├── kms/
│   ├── iam/
│   ├── secrets/
│   ├── observability/
│   └── dns/
└── environments/
    ├── dev/
    ├── staging/
    └── prod/
```

Manage:

- VPC
- Subnets
- Routing
- EKS
- Aurora
- S3
- ECR
- IAM
- KMS
- Secrets Manager
- WAF
- ALB
- Route 53
- ACM
- EventBridge
- SQS
- Monitoring

---

### 5.34.3 GitHub Actions

Pull request:

```text
Lint
→ Type Check
→ Unit Test
→ Integration Test
→ Graph Route Test
→ Migration Check
→ Golden Dataset Evaluation
→ Security Scan
→ Docker Build
→ Terraform Validate
```

Main branch:

```text
Build Image
→ Push ECR
→ Deploy Staging
→ Smoke Test
→ RAG Regression
→ Learning Regression
→ Load Test
→ Approval
→ Production Canary
→ Production Rollout
```

---

## 5.35 Required External Accounts, APIs, and Identifiers

### AWS

- AWS Organization
- Development, staging, and production accounts
- Bedrock model access
- EKS
- Aurora PostgreSQL
- S3
- ECR
- Secrets Manager
- KMS
- Route 53
- ACM
- WAF
- EventBridge
- SQS
- IAM roles
- CloudTrail
- GuardDuty

### Google Cloud

- Google Cloud project
- Gmail API
- Google Calendar API
- Maps JavaScript API or browser geolocation integration
- Geocoding API
- Routes API
- YouTube Data API v3
- OAuth consent screen
- Web OAuth client ID
- Server OAuth client ID
- Restricted Maps API key
- Redirect URIs

### GitHub

- GitHub organization
- Application repositories
- Knowledge-content repository
- GitHub environments
- OIDC federation to AWS
- Protected branches
- Required reviewers
- Secrets or AWS OIDC configuration

### LangSmith

- Enterprise workspace
- Project-specific API keys
- Data-retention configuration
- PII-masking policy
- Self-hosted license or cloud DPA
- Separate development, staging, and production projects

### Domains

- `learning.intellichoice.org`
- `chat.intellichoice.org`
- Optional API domains:
  - `api.learning.intellichoice.org`
  - `api.chat.intellichoice.org`

### Example Secrets

```text
BEDROCK_MODEL_ID
BEDROCK_EMBEDDING_MODEL_ID
LEARNING_MYSQL_URL
CHAT_MYSQL_URL
POSTGRESQL_URI
GMAIL_OAUTH_CLIENT_ID
GMAIL_OAUTH_CLIENT_SECRET
GMAIL_REFRESH_TOKEN
GOOGLE_CALENDAR_CLIENT_ID
GOOGLE_CALENDAR_CLIENT_SECRET
GOOGLE_MAPS_API_KEY
YOUTUBE_API_KEY
LANGSMITH_API_KEY
AUTH_TOKEN_PUBLIC_KEY
KMS_KEY_ARN
```

`LEARNING_MYSQL_URL` / `CHAT_MYSQL_URL` match `.env.example`; staging stores the MySQL
connection as separate `MYSQL_DB_HOST` / `MYSQL_DB_PORT` / `MYSQL_DB_USERNAME` /
`MYSQL_DB_PASSWORD` components (D-092).

Do not store secrets in GitHub repositories or Docker images.

---

## 5.36 Final Technology Placement

**Amended 2026-08-20 (D-004; confirmed at S32 by D-084).** Two cells in the table below name a
runtime that was decided otherwise: `Kubernetes → EKS runtime`, and the `EKS` term inside
`Enterprise-Level Product`. The runtime is ECS Fargate with RDS PostgreSQL + pgvector. Every other
row stands, with three carrying their own markers at their own sections — `LangSmith` (§5.32.1),
`Multimodal` (§5.17) and `Guardrails` (§5.25.1).

**Amended 2026-08-24 (D-438 — the `TEST-05` descriptive re-read, four qualifying changes late).**
Two corrections to the paragraph above's "every other row stands": the `Grafana/Prometheus` row's
Grafana half was decided otherwise — product and infrastructure dashboards are **CloudWatch**
(D-244), while the Prometheus half is as built (`prometheus_client`, EMF-exported per the otel
allowlist) — and the `PostgreSQL` placement row grew a use this table predates: the
**cross-replica SSE event relay** over `LISTEN`/`NOTIFY` (D-334/D-335 learning, D-349 chat).

| Technology | Placement |
|---|---|
| Enterprise-Level Product | Environment isolation, SLOs, RBAC, audit, CI/CD, EKS |
| LangGraph | Both application workflows |
| Multi-Agent Orchestration | Learning agents and Q&A agents |
| State Management | LearningState and QAState |
| Conditional Routing | Attendance, answer correctness, scope, intent |
| Tool Calling | Databases, Gmail, Maps, Calendar, Video |
| Human-in-the-Loop | Hint/solution/video, email, calendar, location |
| Memory | Procedural, episodic, semantic |
| PostgreSQL Checkpointing | Graph pause and resume |
| Graceful Failure | Retry, fallback, circuit breaker |
| Pydantic | API, state, LLM output, tool arguments |
| PostgreSQL | Learning, RAG, memory, evaluation |
| pgvector | Document, video, and similar-problem search |
| Metadata Filtering | Role, branch, year, topic, difficulty |
| Hybrid Search | RAG and video catalog |
| Semantic Search | pgvector |
| Keyword Search | PostgreSQL FTS |
| LlamaIndex | RAG ingestion and retrieval |
| Citation Grounding | Q&A responses |
| Chunking | Structure-aware PDF processing |
| Reranking | Hybrid candidate reordering |
| Structured Responses | All machine-readable LLM outputs |
| AWS Bedrock | LLMs, embeddings, VLMs, judges |
| Guardrails | Content, PII, scope, prompt attacks |
| FastAPI | Both backends |
| Async | Databases, LLMs, MCP, streaming |
| Docker | Service packaging |
| Kubernetes | EKS runtime |
| Terraform | AWS infrastructure |
| GitHub Actions / CI/CD | Testing, evaluation, deployment |
| Regression Testing | Release gate |
| Golden Dataset | Learning and Q&A |
| LLM-as-a-Judge | Educational and language quality |
| Deterministic Evaluator | Scores, permissions, routing |
| Executable Evaluator | Math, ICS, SQL, schemas |
| LangSmith | Agent traces and evaluation |
| LangFuse | Not used |
| Tracing | End-to-end request tracing |
| Logging | PII-safe structured logs |
| OpenTelemetry | Distributed telemetry |
| Grafana/Prometheus | Product and infrastructure metrics |
| YouTube MCP/API | Weekly API sync and internal catalog search |
| Gmail MCP | Attendance and admin escalation |
| Google Maps MCP | Nearest-branch search |
| Calendar MCP | Google Calendar events and Apple `.ics` |
| PII Handling | Database separation, masking, retention |
| Multimodal | Solution-image analysis with immediate deletion |

---

# 6. Updated Recommended Implementation Sequence

**Historical as of 2026-08-20 (`RISK-R1.4-SPEC-VINTAGE`, `AMENDMENT-SWEEP`).** The 24-phase
sequence below is retained in place as the original planning record and is **no longer the plan of
record**. ROADMAP's per-session "Done when" criteria superseded it, and ROADMAP is now at
`docs/archive/ROADMAP.md`. Read §6 for design intent and for what a phase was meant to prove; do
not read it as an open work list, a phase numbering anyone still uses, or a statement of what is
built. Nothing in §5 is affected by this demotion — §5 stays normative.

## 6.1 Phase 0: Legal, Policy, and Data Contracts

### Objective

Define legal boundaries and data ownership before implementation.

### Work

- Privacy Notice
- AI Use Notice
- Product-specific Learning Notice
- Parent Access Policy
- Data Retention Policy
- Immediate Image Deletion Policy
- Subprocessor List
- Incident Response Policy
- Acceptable Use Policy
- Tutor and Manager Access Policy
- COPPA and FERPA applicability review
- State student-privacy review

### Completion Criteria

- Consent claims from `go.intellichoice.org` are finalized.
- MySQL and PostgreSQL ownership is finalized.
- Production data-flow diagram is approved.
- Legal review items are documented.

---

## 6.2 Phase 1: Organization Accounts and Environment Setup

### Objective

Create enterprise-grade development, staging, and production separation.

### Work

- AWS Organization and accounts
- Google Cloud projects
- GitHub organization
- Domain and DNS access
- LangSmith workspace
- GitHub OIDC to AWS
- Environment-specific secrets
- Bedrock model-access requests

### Completion Criteria

Each environment uses separate credentials and resources.

---

## 6.3 Phase 2: Terraform-Based AWS Foundation

### Objective

Create shared infrastructure as code.

### Work

- VPC
- Private and public subnets
- EKS
- Aurora PostgreSQL
- S3
- ECR
- KMS
- WAF
- ALB
- Route 53
- ACM
- SQS
- EventBridge
- CloudTrail
- Monitoring

### Completion Criteria

The development environment can be recreated from Terraform.

---

## 6.4 Phase 3: Existing Authentication and MySQL Profile Adapter

### Objective

Allow both applications to reuse the existing login system safely.

### Work

- Validate existing auth tokens
- Separate application audiences
- Read-only MySQL adapter
- Parent-child lookup
- Grade lookup
- Branch lookup
- Real-time attendance lookup
- Branch-manager email lookup
- Authorization middleware

### Completion Criteria

- Students are authenticated as themselves.
- Parents can select only linked children.
- Tutor and manager roles resolve correctly.
- PostgreSQL contains no replicated PII.

---

## 6.5 Phase 4: PostgreSQL Domain Schema

### Objective

Build the domain model before LLM features.

### Work

- Curriculum
- Topics and skills
- Question templates
- Question variants
- Assessments
- Attempts
- Mastery
- Study sessions
- Learning gain
- Problem reports
- Memory
- RAG
- Evaluation
- Alembic migrations

### Completion Criteria

All domain tables and indexes are reproducibly created through migrations.

---

## 6.6 Phase 5: Curriculum Taxonomy and Seed Question Bank

### Objective

Prepare the math curriculum and validated multiple-choice questions.

### Work

- Organize public Kumon level and topic references
- Define internal topic and skill taxonomy
- Map grade to candidate topics
- Generate 100 templates per topic
- Create 20 templates per difficulty
- Build Question Generator
- Build Solver Agents A and B
- Build Difficulty Reviewer
- Build Ambiguity Reviewer
- Build Executable Validator
- Build Quarantine workflow

### Technologies

- AWS Bedrock
- Structured Outputs
- Pydantic
- Multi-Agent
- Executable Evaluator

### Completion Criteria

Every active question has exactly one correct answer and passes all automated checks.

---

## 6.7 Phase 6: Deterministic Learning Vertical Slice

### Objective

Complete the learning flow without LLM dependency.

```text
Login
→ Student selection
→ Attendance
→ Topic selection
→ Pre-exam
→ Deterministic scoring
→ Fixed study questions
→ Post-exam
→ Learning gain
```

### Technologies

- FastAPI
- PostgreSQL
- MySQL
- Deterministic Evaluator
- Idempotency

### Completion Criteria

A student can complete the entire flow through APIs.

---

## 6.8 Phase 7: LangGraph Workflow and Checkpointing

### Objective

Convert learning and Q&A into stateful graphs.

### Work

- LearningState
- QAState
- Conditional routing
- PostgresSaver
- Thread ID
- Resume API
- Attendance branches
- Error branches
- Timeout branches

### Technologies

- LangGraph
- State management
- PostgreSQL checkpointing
- Graceful failure

### Completion Criteria

Sessions resume after pod restart or browser refresh.

---

## 6.9 Phase 8: Human-in-the-Loop

### Objective

Use interrupts for all approval-sensitive actions.

### Work

- Child selection
- Attendance-email approval
- Hint/solution/video selection
- Location consent
- Calendar approval
- Admin email approval
- Image-analysis consent

### Technologies

- LangGraph `interrupt()`
- PostgreSQL checkpointing
- Pydantic

### Completion Criteria

No external action can execute before approval.

---

## 6.10 Phase 9: Bedrock Tutor and Structured Responses

### Objective

Add personalized explanation and follow-up support.

### Work

- Bedrock Gateway
- Tutor Agent
- Hint Generator
- Solution Generator
- Topic Resolver
- Scope Classifier
- Intent Router
- Parent Report Generator
- Bedrock Guardrails
- Pydantic validation

### Completion Criteria

- JSON Schema adherence meets target.
- Early answer leakage is controlled.
- Grade-appropriate explanation passes evaluation.
- Safe fallbacks work.

---

## 6.11 Phase 10: Adaptive Mastery and Study Planner

### Objective

Adapt question selection from pre-exam results.

### Work

- Weighted score
- Skill mastery
- Difficulty routing
- Remediation questions
- Maximum-attempt policy
- Tutor flags
- Post-exam parallel forms
- Learning gain

### Completion Criteria

Scores and routing are reproducible for identical inputs.

---

## 6.12 Phase 11: Real-Time Learning UI

### Objective

Display real-time learning progress.

### Work

- SSE
- LangGraph event streaming
- Progress bar
- Topic progress
- Difficulty
- Streak
- Remaining questions
- Hint, solution, and video counts
- Pre/post results
- Mastery visualization
- Parent dashboard

### Completion Criteria

Progress is restored correctly after refresh.

---

## 6.13 Phase 12: Tutor and Branch Manager Integration with the Existing Site

### Objective

Expose only necessary summaries through `go.intellichoice.org`.

### Work

- Server-to-server Learning Summary API
- `go.intellichoice.org` integration
- Role validation
- Branch scoping
- Score and skill-summary DTOs
- Audit logging

### Completion Criteria

- Tutors and managers see only approved summaries.
- Full chats and parent reports are unavailable.
- Cross-branch access is blocked.

---

## 6.14 Phase 13: RAG Content Foundation

### Objective

Create safe seed content and an ingestion pipeline.

### Work

- Knowledge-content repository
- Placeholder documents
- Manifests
- S3 buckets
- Approved/draft separation
- Annual versions
- LlamaIndex ingestion
- Chunking
- Metadata
- Embeddings

### Completion Criteria

The production retriever searches only approved documents.

---

## 6.15 Phase 14: Advanced RAG

### Objective

Build role-aware and branch-aware grounded Q&A.

### Work

- Metadata filtering
- PostgreSQL full-text search
- pgvector search
- Hybrid search
- Reciprocal Rank Fusion
- Reranking
- Citation grounding
- Conflict detection
- No-answer policy
- Prompt-injection defense

### Completion Criteria

- Core claims have citations.
- Unauthorized documents are never retrieved.
- The system does not guess without evidence.

---

## 6.16 Phase 15: MCP Integration

Implementation order:

1. Gmail MCP
2. Google Maps MCP
3. Google Calendar MCP
4. `.ics` generator
5. Internal YouTube Catalog MCP

### Work

- MCP registry
- Tool schemas
- Timeouts
- Retries
- Permissions
- User approval
- Audit events
- Fallbacks

### Completion Criteria

Only Pydantic-validated tool arguments can execute.

---

## 6.17 Phase 16: Weekly YouTube Sync

### Objective

Maintain a verified video catalog without real-time external search.

### Work

- YouTube Data API
- EventBridge schedule
- SQS
- Sync worker
- Upsert logic
- Removed-video handling
- Topic and skill mapping
- Embeddings
- Video retrieval tool

### Completion Criteria

- Runs automatically every week.
- Keeps the previous catalog on failure.
- Makes no YouTube API calls during learning.

---

## 6.18 Phase 17: Memory System

### Objective

Separate procedural, episodic, and semantic memory.

### Work

- Procedural-policy versioning
- Episodic-event schema
- Raw-chat retention
- Semantic-fact schema
- Sunday consolidation
- Evidence links
- Confidence
- Fact expiration

### Technologies

- LangGraph memory
- PostgreSQL
- Bedrock summarizer
- EventBridge
- SQS
- Pydantic

### Completion Criteria

No semantic fact is stored without evidence.

---

## 6.19 Phase 18: Multimodal

### Objective

Analyze student solution images without retaining them.

### Work

- File validation
- Malware scanning
- Ephemeral storage
- VLM analysis
- Formula extraction
- Step analysis
- Executable verification
- Immediate deletion
- Deletion metric

### Technologies

- Bedrock VLM
- Pydantic
- Executable Evaluator
- PII handling

### Completion Criteria

- Images are deleted immediately.
- Images do not appear in backups, LangSmith, or logs.
- VLM output does not change the multiple-choice score.

---

## 6.20 Phase 19: Evaluation Platform

### Objective

Automatically compare model, prompt, RAG, and graph changes.

### Work

- Golden dataset
- Deterministic evaluation
- Executable evaluation
- LLM-as-a-Judge
- Baselines
- Regression thresholds
- Cost and latency checks
- Question-quality evaluation

### Technologies

- LangSmith datasets
- Regression testing
- LLM-as-a-Judge
- Pytest

### Completion Criteria

GitHub Actions blocks deployment when evaluation thresholds are not met.

---

## 6.21 Phase 20: Observability

### Objective

Trace each request across the system.

### Work

- LangSmith
- OpenTelemetry
- JSON logging
- PII masking
- Prometheus
- Grafana
- Alerting
- Product KPIs
- Cost dashboards

### Completion Criteria

```text
Frontend
→ FastAPI
→ LangGraph
→ Bedrock
→ MySQL/PostgreSQL
→ MCP
```

The full path is visible under one `trace_id`.

---

## 6.22 Phase 21: Security Hardening

### Work

- AWS WAF
- Rate limiting
- CAPTCHA
- RBAC
- NetworkPolicy
- Pod security
- Secret rotation
- OAuth scope review
- Dependency scanning
- Container scanning
- Penetration testing
- Prompt-injection testing
- Data-deletion testing
- Image-deletion testing
- Backup and restore testing
- Incident-response drills

### Completion Criteria

Security and legal reviews are production release gates.

---

## 6.23 Phase 22: Load Testing and Production Readiness

### Load Targets

- More than 1,000 students
- More than 100 concurrent learning sessions
- More than 100 SSE connections
- Concurrent Bedrock requests
- Parallel MySQL/PostgreSQL reads
- Queue bursts
- MCP timeouts

### Tests

- k6 or Locust
- Pod failure
- Database failover
- Bedrock throttling
- MySQL timeout
- MCP outage
- Queue backlog
- Rolling deployment

### Completion Criteria

- 99.9% monthly SLO architecture validated
- General API P95 target met
- LLM TTFT target validated
- No data loss during retries
- Checkpoint resume succeeds

---

## 6.24 Phase 23: Production CI/CD

```text
Pull Request
→ Static Analysis
→ Unit Tests
→ Integration Tests
→ Graph Tests
→ Golden Evaluation
→ Security Scan
→ Docker Build
→ Terraform Plan
→ Staging Deploy
→ Smoke Test
→ Load Test
→ Compliance Approval
→ Production Canary
→ Metric Check
→ Full Rollout
```

Rollback triggers:

- Error-rate increase
- P95 latency degradation
- Structured-output failure increase
- RAG citation-accuracy decrease
- Learning-completion decline
- PII leak detection
- Tool malfunction
- Image-deletion failure

---

## 6.25 Practical Development Priority

### Product Core

```text
Auth/MySQL Adapter
→ PostgreSQL
→ Deterministic Assessment
→ LangGraph
→ Checkpoint/HITL
```

### Intelligence

```text
Bedrock Structured Output
→ Tutor Agent
→ Adaptive Mastery
→ Parent Report
→ Memory
```

### Knowledge and Tools

```text
RAG
→ Gmail
→ Maps
→ Calendar
→ YouTube Catalog
```

### Enterprise Quality

```text
Evaluation
→ Observability
→ Security
→ Legal Review
→ Load Test
```

### Production Operations

```text
Docker
→ GitHub Actions
→ EKS
→ Terraform
→ Canary Deployment
```

The most important principle is to implement accurate domain logic first: attendance, authorization, grading, question quality, and learning results. Agent orchestration, RAG, MCP tools, memory, and infrastructure should be added incrementally after the product core is reliable.
