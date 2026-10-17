# Exploratory development comparison

Reference: base. Differences below are arm minus reference.
One inference seed; training seed variation is not estimable. Final test remains unopened.

| Arm | Status | action_macro_f1 | guard_valid_action_macro_f1 | stale_active_rate | missing_state_rate | false_overwrite_rate | erroneous_mutations_among_commits | state_exact_match | deterministic_qa_exact_match |
|---|---|---|---|---|---|---|---|---|---|
| rule | evaluated | 1.0000 | 1.0000 | 0.0000 (0/38) | 0.0000 (0/103) | 0.0000 (0/26) | 0.0000 (0/44) | 1.0000 (103/103) | 1.0000 (103/103) |
| base | evaluated | 0.0500 | 0.0000 | 0.0000 (0/38) | 1.0000 (103/103) | 0.0000 (0/26) | undefined (0/0) | 0.0000 (0/103) | 0.0000 (0/103) |
| sft-default | evaluated | 0.2610 | 0.2772 | 0.0000 (0/38) | 0.8447 (87/103) | 0.0769 (2/26) | 0.0385 (1/26) | 0.1359 (14/103) | 0.0000 (0/103) |
| sft-adjusted | evaluated | 0.4736 | 0.5126 | 0.3947 (15/38) | 0.0000 (0/103) | 0.0000 (0/26) | 0.0833 (1/12) | 0.7282 (75/103) | 0.2816 (29/103) |
| latest-arrival (diagnostic) | evaluated | 0.6624 | 0.7228 | 0.3158 (12/38) | 0.0000 (0/103) | 0.0000 (0/26) | 0.0303 (1/33) | 0.8835 (91/103) | 0.8835 (91/103) |

## Paired trajectory uncertainty

95% percentile intervals; pooled counts after resampling complete trajectories. Undefined draws are excluded and counted.

| Arm | Metric | Difference | 95% interval | Undefined draws |
|---|---|---|---|---|
| rule | stale_active_rate | 0.0 | [0.0, 0.0] | 19/2000 |
| rule | missing_state_rate | -1.0 | [-1.0, -1.0] | 0/2000 |
| rule | state_exact_match | 1.0 | [1.0, 1.0] | 0/2000 |
| rule | false_overwrite_rate | 0.0 | [0.0, 0.0] | 0/2000 |
| rule | erroneous_mutations_among_commits | None | [None, None] | 2000/2000 |
| rule | invalid_output_rate | -0.9431818181818182 | [-1.0, -0.8804347826086957] | 0/2000 |
| rule | provenance_precision | None | [None, None] | 2000/2000 |
| rule | provenance_recall | 1.0 | [1.0, 1.0] | 0/2000 |
| rule | parse_invalid_rate_gold_history | -0.8863636363636364 | [-1.0, -0.7608695652173914] | 0/2000 |
| rule | validator_rejection_rate_gold_history | -1.0 | [-1.0, -1.0] | 153/2000 |
| rule | parse_invalid_rate_closed_loop | -1.0 | [-1.0, -1.0] | 0/2000 |
| rule | validator_rejection_rate_closed_loop | None | [None, None] | 2000/2000 |
| rule | mechanical_provenance_validity | 1.0 | [1.0, 1.0] | 0/2000 |
| rule | state_exact_match_current | 1.0 | [1.0, 1.0] | 0/2000 |
| rule | state_exact_match_historical_or_future | 1.0 | [1.0, 1.0] | 0/2000 |
| rule | deterministic_qa_exact_match | 1.0 | [1.0, 1.0] | 0/2000 |
| sft-default | stale_active_rate | 0.0 | [0.0, 0.0] | 19/2000 |
| sft-default | missing_state_rate | -0.15533980582524276 | [-0.43999999999999995, 0.0] | 0/2000 |
| sft-default | state_exact_match | 0.13592233009708737 | [0.0, 0.42] | 0/2000 |
| sft-default | false_overwrite_rate | 0.07692307692307693 | [0.0, 0.11764705882352941] | 0/2000 |
| sft-default | erroneous_mutations_among_commits | None | [None, None] | 2000/2000 |
| sft-default | invalid_output_rate | -0.6931818181818182 | [-0.8222222222222222, -0.5581395348837208] | 0/2000 |
| sft-default | provenance_precision | None | [None, None] | 2000/2000 |
| sft-default | provenance_recall | 0.06829268292682927 | [0.0, 0.15328467153284672] | 0/2000 |
| sft-default | parse_invalid_rate_gold_history | -0.6818181818181818 | [-0.888888888888889, -0.4772727272727273] | 0/2000 |
| sft-default | validator_rejection_rate_gold_history | -0.9142857142857143 | [-1.0, -0.8181818181818181] | 153/2000 |
| sft-default | parse_invalid_rate_closed_loop | -0.7045454545454546 | [-0.8181818181818181, -0.5681818181818181] | 0/2000 |
| sft-default | validator_rejection_rate_closed_loop | None | [None, None] | 2000/2000 |
| sft-default | mechanical_provenance_validity | 0.7045454545454546 | [0.5681818181818182, 0.8181818181818182] | 0/2000 |
| sft-default | state_exact_match_current | 0.1590909090909091 | [0.0, 0.44680851063829785] | 0/2000 |
| sft-default | state_exact_match_historical_or_future | 0.11864406779661017 | [0.0, 0.39622641509433965] | 0/2000 |
| sft-default | deterministic_qa_exact_match | 0.0 | [0.0, 0.0] | 0/2000 |
| sft-adjusted | stale_active_rate | 0.39473684210526316 | [0.0, 0.9] | 19/2000 |
| sft-adjusted | missing_state_rate | -1.0 | [-1.0, -1.0] | 0/2000 |
| sft-adjusted | state_exact_match | 0.7281553398058253 | [0.40594059405940597, 1.0] | 0/2000 |
| sft-adjusted | false_overwrite_rate | 0.0 | [0.0, 0.0] | 0/2000 |
| sft-adjusted | erroneous_mutations_among_commits | None | [None, None] | 2000/2000 |
| sft-adjusted | invalid_output_rate | -0.9431818181818182 | [-1.0, -0.8804347826086957] | 0/2000 |
| sft-adjusted | provenance_precision | None | [None, None] | 2000/2000 |
| sft-adjusted | provenance_recall | 0.4097560975609756 | [0.30656934306569344, 0.6] | 0/2000 |
| sft-adjusted | parse_invalid_rate_gold_history | -0.8863636363636364 | [-1.0, -0.7608695652173914] | 0/2000 |
| sft-adjusted | validator_rejection_rate_gold_history | -0.31818181818181823 | [-0.4666666666666667, -0.18181818181818177] | 153/2000 |
| sft-adjusted | parse_invalid_rate_closed_loop | -1.0 | [-1.0, -1.0] | 0/2000 |
| sft-adjusted | validator_rejection_rate_closed_loop | None | [None, None] | 2000/2000 |
| sft-adjusted | mechanical_provenance_validity | 1.0 | [1.0, 1.0] | 0/2000 |
| sft-adjusted | state_exact_match_current | 0.7272727272727273 | [0.4146341463414634, 1.0] | 0/2000 |
| sft-adjusted | state_exact_match_historical_or_future | 0.7288135593220338 | [0.4117647058823529, 1.0] | 0/2000 |
| sft-adjusted | deterministic_qa_exact_match | 0.2815533980582524 | [0.12149532710280374, 0.5178571428571429] | 0/2000 |
| latest-arrival | stale_active_rate | 0.3157894736842105 | [0.0, 0.8] | 19/2000 |
| latest-arrival | missing_state_rate | -1.0 | [-1.0, -1.0] | 0/2000 |
| latest-arrival | state_exact_match | 0.883495145631068 | [0.6756756756756757, 1.0] | 0/2000 |
| latest-arrival | false_overwrite_rate | 0.0 | [0.0, 0.0] | 0/2000 |
| latest-arrival | erroneous_mutations_among_commits | None | [None, None] | 2000/2000 |
| latest-arrival | invalid_output_rate | -0.9431818181818182 | [-1.0, -0.8804347826086957] | 0/2000 |
| latest-arrival | provenance_precision | None | [None, None] | 2000/2000 |
| latest-arrival | provenance_recall | 0.9414634146341463 | [0.788235294117647, 1.0] | 0/2000 |
| latest-arrival | parse_invalid_rate_gold_history | -0.8863636363636364 | [-1.0, -0.7608695652173914] | 0/2000 |
| latest-arrival | validator_rejection_rate_gold_history | -0.7272727272727273 | [-0.8478260869565217, -0.5952380952380952] | 153/2000 |
| latest-arrival | parse_invalid_rate_closed_loop | -1.0 | [-1.0, -1.0] | 0/2000 |
| latest-arrival | validator_rejection_rate_closed_loop | None | [None, None] | 2000/2000 |
| latest-arrival | mechanical_provenance_validity | 1.0 | [1.0, 1.0] | 0/2000 |
| latest-arrival | state_exact_match_current | 0.8863636363636364 | [0.6590909090909091, 1.0] | 0/2000 |
| latest-arrival | state_exact_match_historical_or_future | 0.8813559322033898 | [0.676923076923077, 1.0] | 0/2000 |
| latest-arrival | deterministic_qa_exact_match | 0.883495145631068 | [0.6756756756756757, 1.0] | 0/2000 |

## Limitations

- exploratory synthetic annotated development data
- two development probes previously inspected
- neither educational adapter passed twenty-target overfit
- no human label review
- no final generalization or research-superiority claim
- intervals conditional on this tiny development sample
- equal-token/no-correction research controls and guard-removal sandbox deferred; unconstrained decoding only
