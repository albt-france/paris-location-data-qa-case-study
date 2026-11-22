-- 07_annotator_agreement.sql : pairwise agreement and Cohen's kappa, before (v1) and after (v2) the guideline change.
-- kappa = (p_o - p_e) / (1 - p_e); p_o = observed agreement, p_e = agreement expected by chance from each
-- annotator's own verdict distribution.
CREATE OR REPLACE TABLE pairs AS
SELECT a.guidelines_version, a.annotator_id AS r_a, b.annotator_id AS r_b, a.answer_id, q.query_type,
       a.verdict AS v_a, b.verdict AS v_b
FROM annotations a
JOIN annotations b ON a.answer_id = b.answer_id AND a.annotator_id < b.annotator_id
JOIN answers q ON q.answer_id = a.answer_id;

CREATE OR REPLACE TABLE agreement AS
WITH base AS (
  SELECT guidelines_version, r_a, r_b, 'all answers' AS scope, v_a, v_b FROM pairs
  UNION ALL
  SELECT guidelines_version, r_a, r_b, 'opening_status only', v_a, v_b FROM pairs WHERE query_type = 'opening_status'),
po AS (
  SELECT guidelines_version, r_a, r_b, scope, count(*) AS n, avg(CASE WHEN v_a = v_b THEN 1.0 ELSE 0 END) AS p_o
  FROM base GROUP BY ALL),
marg AS (
  SELECT guidelines_version, r_a, r_b, scope, cat,
         avg(CASE WHEN v_a = cat THEN 1.0 ELSE 0 END) AS pa, avg(CASE WHEN v_b = cat THEN 1.0 ELSE 0 END) AS pb
  FROM base, (VALUES ('correct'), ('minor_issue'), ('major_issue'), ('cannot_verify')) c(cat)
  GROUP BY ALL),
pe AS (SELECT guidelines_version, r_a, r_b, scope, sum(pa * pb) AS p_e FROM marg GROUP BY ALL)
SELECT po.scope, po.guidelines_version, po.r_a || '-' || po.r_b AS pair, po.n,
       round(po.p_o, 3) AS observed_agreement, round(pe.p_e, 3) AS chance_agreement,
       round((po.p_o - pe.p_e) / (1 - pe.p_e), 3) AS cohen_kappa
FROM po JOIN pe USING (guidelines_version, r_a, r_b, scope)
ORDER BY scope, pair, guidelines_version;

-- Confusion matrix R1 (rows) x R2 (columns), per guideline version
CREATE OR REPLACE TABLE confusion_r1_r2 AS
SELECT guidelines_version, v_a AS r1_verdict,
       sum(CASE WHEN v_b = 'correct' THEN 1 ELSE 0 END) AS r2_correct,
       sum(CASE WHEN v_b = 'minor_issue' THEN 1 ELSE 0 END) AS r2_minor_issue,
       sum(CASE WHEN v_b = 'major_issue' THEN 1 ELSE 0 END) AS r2_major_issue,
       sum(CASE WHEN v_b = 'cannot_verify' THEN 1 ELSE 0 END) AS r2_cannot_verify
FROM pairs WHERE r_a = 'R1' AND r_b = 'R2'
GROUP BY guidelines_version, v_a
ORDER BY guidelines_version, list_position(['correct', 'minor_issue', 'major_issue', 'cannot_verify'], any_value(v_a));

CREATE OR REPLACE TABLE time_per_task AS
SELECT guidelines_version, annotator_id, count(*) AS tasks, median(seconds) AS median_s,
       quantile_cont(seconds, 0.9) AS p90_s
FROM annotations GROUP BY ALL ORDER BY guidelines_version, annotator_id;

SELECT scope, guidelines_version, round(avg(cohen_kappa), 3) AS mean_kappa FROM agreement GROUP BY ALL ORDER BY ALL;
