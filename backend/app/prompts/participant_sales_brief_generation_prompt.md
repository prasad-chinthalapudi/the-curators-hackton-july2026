# PIH Hackathon Sales Brief Generation Prompt

Use this prompt to generate the required project one-pager / sales brief from the provided PIH hackathon materials.

```text
You are generating the required PIH Hackathon project one-pager / sales brief.

Goal:
Create a polished, shareable, one-page sales brief for one single project found in the provided project materials. The brief must be generated from the source materials, not written from imagination or from a fixed generic template.

Audience:
Write for Blend360 sales, delivery, and account teams who need to quickly understand a past project and reuse it as a credible capability story in a sales conversation.

Project to brief:
[ENTER PROJECT NAME OR CASE STUDY NAME HERE]

Source materials available:
[PASTE OR LIST THE FILES, EXTRACTED TEXT, SLIDE NOTES, OR SEARCH RESULTS USED HERE]

Hard rules:
1. Use only facts supported by the provided materials.
2. Do not invent client names, dates, technologies, metrics, outcomes, team roles, project owners, or business impact.
3. If a required section is not supported by the materials, include a short "Known gap" note for that section instead of guessing.
4. Make the brief read like a short case study or sales brief, not like raw notes.
5. Keep it concise enough to fit on one page.
6. Make the value clear for a sales or delivery reader.
7. Prefer specific, quantified outcomes when the source supports them.
8. Include visible source references for important claims, especially metrics, technologies, client/project names, and outcomes.
9. If source evidence conflicts, use the most final/current project material when clear, and mention the conflict briefly in "Known gaps / caveats."
10. The output must be usable as a submission artifact for the PIH Hackathon.

Required structure:

Title:
Use the project name plus a short descriptor of what the project was.
Example style: "ML Data Science Model Workflows in Snowflake - Norwegian Cruise Line (NCL)"

Generated on:
Use today's date or the date the brief is generated.
Format: "Generated [DATE] - Sales Brief"

Case study line:
Write one line identifying the client/project as a Blend360 case study.

Executive summary:
Write 1-2 short paragraphs explaining:
- who Blend360 helped
- what problem or opportunity the work addressed
- what was delivered
- the headline business or technical outcomes

The challenge:
Explain the situation before the work:
- operational pain points
- fragmented tools, manual work, slow process, knowledge gaps, cost, risk, or missed opportunity
- why the client needed a better approach

Our solution:
Explain what Blend360 built or delivered:
- core platform, workflow, model, analytics, automation, data foundation, agent, or process
- relevant technology stack
- how the team or delivery model was set up, if the materials support it

Key features:
List 3-5 specific capabilities delivered. For each feature, use this format:
- Feature Name - one concise sentence explaining what it does and why it matters.

Quantified outcomes:
List measurable results found in the materials. Include only sourced metrics.
Examples of valid metrics: time reduction, cost reduction, revenue impact, accuracy, speed, adoption, coverage, volume, processing time, number of models, number of features.
If no metrics are available, write: "Known gap: the provided materials do not include quantified outcomes."

Business value:
Explain why this project matters in a sales conversation:
- what proof point it gives Blend360
- what buyer concern it helps answer
- what reusable capability it demonstrates

Known gaps / caveats:
List any missing information that the materials do not answer.
For each gap, write:
- what is missing
- who or what type of owner should be asked if known
- how the answer would improve the brief

Sources used:
List the source files, slides, pages, or excerpts used. Be as specific as the materials allow.

Writing style:
- Clear, executive, and business-facing.
- No hype without evidence.
- No internal implementation jargon unless it is central to the project.
- Use short paragraphs and scannable bullets.
- Keep the brief polished but grounded.
- Do not say "based on the provided materials" repeatedly; just cite sources where useful.

Final output format:
Return the completed sales brief in Markdown using these exact section headings:

# [Title]
Generated [DATE] - Sales Brief

[Client / Project] - A Blend360 Case Study

## Executive Summary

## The Challenge

## Our Solution

## Key Features

## Quantified Outcomes

## Business Value

## Known Gaps / Caveats

## Sources Used
```
