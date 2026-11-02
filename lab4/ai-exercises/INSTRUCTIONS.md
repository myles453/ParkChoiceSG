# Coding-agent exercise instructions applied in this task

Date: 26 October 2026. These are operational instructions prepared for the
user's request to complete the Lab 4 deliverables. They are not quoted as a
separate message typed by a student and are not a reconstructed chat transcript.

## Exercise 3.3.2: reconstruct a control class

Reconstruct the missing `RecommendationController` in a disposable copy of
`backend/recommendation.py`. The entire class must be absent, not merely its
method bodies. Use the existing module helpers, data contracts and the frozen
black-box cases in `test_lab4_controller.py`. Do not read a backup of the removed
class, change tests, call real providers, modify the database or replace the
working application during this experiment.

Required API: `RecommendationController(router, predictor=None).recommend(request)`.
The result must preserve candidate details, ranking exclusions, provisional
ranking-mode policy metadata, and separate current-only fallback. Do not invent
predictions, supported tariffs or routes. A low probability must not be rescued
through current fallback. Retain forecast-before-outcome audit behavior.

Record the missing-class failure and the regenerated class's actual test results.
Keep the working implementation unchanged. Report failures and additional
iterations honestly.

The assistant is the ongoing project coding assistant and has previously seen
the project implementation. This is an isolated removal/reconstruction exercise,
not an independently blinded or fresh-session evaluation. No claim is made that
the tests were originally written without AI assistance.

## Exercise 3.3.3: refactor and regression-check

Review the recommendation orchestration against the design's control class.
Extract the existing coordination behavior into a small `RecommendationController`,
retain the public `recommend(...)` function as a compatibility entry point, and
keep pricing, collection and scoring helpers in their current modules. Avoid
new frameworks, repositories or service processes. Check the existing regression
suite and the newly specified controller cases. Record the scope and outcome.

The code and tests, along with the local Lab 4 manual, were provided through
the ongoing assistant conversation and file inspection. The reflections must
describe these actual actions without inventing user prompts, student feelings
or an exact model identifier.
