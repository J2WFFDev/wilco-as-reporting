# Customer 1: Wilco Shooting Sports Internal Use

## Purpose

Build a Wilco-specific match operations and analytics package that helps coaches prepare, execute, and review SASP matches.

Wilco's goal is not just reporting. It is athlete development, coach execution, Nationals readiness, and long-term competitive improvement.

## Primary audience

- Head Coach
- Assistant Coaches
- Team leadership
- Athletes and parents, where appropriate

## Core questions

- How did Wilco perform?
- Who needs coaching attention?
- Who is outperforming expectations?
- Which athletes are close to podium thresholds?
- Which squads are competitive?
- What should coaches know while standing at a stage?
- What stories should be shared after the match?

## Required report packages

### 1. Wilco Match Operations Workbook

Coach-facing workbook with:

- Dashboard
- Registered athletes
- Match scores
- Rankings
- Stage Coach View
- Athlete Stage Matrix
- Squad Report
- Squad Members
- Wilco vs Field
- Match Records
- Highlights
- Score Audit Summary

### 2. Stage Coach View

Purpose: help coaches give useful feedback during a match.

For each athlete, discipline, and stage:

- Fastest String
- Scored Avg String
- Stage Score
- Best Historical Stage Score
- Avg Historical Stage Score
- Coach cue

Official coach-facing average should use the four counting strings.

### 3. Athlete Stage Matrix

For each athlete, discipline, and stage:

- Fastest String
- Avg String
- Fastest Stage Score
- Avg Stage Score
- Best Match Score
- Avg Match Score

Do not include Best 1st Shot because it is not available in the SASP JSON.

### 4. Match Records

Only include record-worthy metrics:

- Fastest Individual String by actual stage name
- Fastest Stage Score by actual stage name
- Lowest Match Score by discipline
- Closest Finish, individual or squad

Do not use derived records such as average match pace.

### 5. Squad Report

Flattened one-row-per-squad view:

- Match
- Discipline
- Rank Scope
- Squad Place
- Squad Name
- Squad Score
- Margin to Leader
- Margin to Previous Place
- Margin to Podium Cutoff
- Athlete 1 / Score 1
- Athlete 2 / Score 2
- Athlete 3 / Score 3
- Athlete 4 / Score 4
- Squad detail text

### 6. Highlights

Highlights should be story-quality, not raw leaderboard duplication.

Collapse repeated highlights by:

- Athlete
- Discipline
- Score

Use hierarchy:

1. Overall Champion
2. Overall Runner-Up
3. Close to Overall Win
4. Overall Top 5
5. Division Winner
6. Gender Winner
7. Podium / Award
8. Near Award Miss
9. Photo Finish
10. Squad Podium
11. Squad Near Miss
12. Team Best
13. Personal Record
14. Team Record

Near Award Miss should only apply when place is outside award places but within a defined margin of the award cutoff.

## Wilco-specific metrics

- Gap to Winner
- Gap to Podium
- Gap to Championship
- Wilco vs Field
- Wilco Top 4 Avg
- Wilco Best vs Field Best
- Team MVP candidates
- Personal Records
- Tentative Wilco Team Records
- Clutch Index
- Consistency Index
- Stage Strengths

## Continue development here

Use this customer stream for anything tailored to Wilco's coaching model, athlete development, internal reports, Nationals readiness, and team storytelling.
