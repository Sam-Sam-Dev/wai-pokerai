# Random opponent benchmark — 100 batches

10,000 complete tournament matches. Each batch ran the shell script for 100 matches with eight selected example opponents plus myAI. All findings below come from saved terminal output.

| Measure | Result |
|---|---:|
| Mean tournament win rate | 12.74% |
| 95% bootstrap interval across batches | 10.48–15.25% |
| Mean final place, out of nine | 3.541 |
| Mean final chips | 229.32 |
| Median batch win rate | 9.5% |
| Lowest–highest batch win rate | 0.0–55.0% |
| Zero-win batches | 5 |
| Batches leading or tied for best win rate | 16 |
| Reported bad actions | 0 |

The bootstrap interval resamples whole 100-match batches, reflecting variation in the selected opponent lineups. It is not an estimate of performance against every possible bot.

## Opponent associations

| Opponent | Batches present | myAI wins when present | myAI wins when absent | Difference | Opponent’s own win rate when selected |
|---|---:|---:|---:|---:|---:|
| raise_by_big_blind_unless_raised | 46 | 3.87% | 20.30% | -16.43 pp | 12.54% |
| exploiter | 43 | 7.37% | 16.79% | -9.42 pp | 45.95% |
| bill_chen | 41 | 10.00% | 14.64% | -4.64 pp | 20.29% |
| real_play_statistics | 48 | 11.52% | 13.87% | -2.34 pp | 22.42% |
| player_notes | 37 | 11.57% | 13.43% | -1.86 pp | 14.73% |
| sklansky_and_malmuth | 37 | 11.92% | 13.22% | -1.30 pp | 20.78% |
| raise_by_half_of_stack | 45 | 12.91% | 12.60% | +0.31 pp | 10.60% |
| call_preflop | 39 | 13.03% | 12.56% | +0.47 pp | 0.23% |
| raise_by_pot | 46 | 13.24% | 12.31% | +0.92 pp | 9.39% |
| call_when_blind | 35 | 13.66% | 12.25% | +1.41 pp | 4.20% |
| phil_hellmuth | 42 | 13.98% | 11.84% | +2.13 pp | 19.60% |
| call | 43 | 14.02% | 11.77% | +2.25 pp | 3.30% |
| go_all_in | 56 | 13.79% | 11.41% | +2.38 pp | 9.20% |
| call_when_big_blind | 50 | 14.66% | 10.82% | +3.84 pp | 1.98% |
| default | 51 | 15.04% | 10.35% | +4.69 pp | 0.00% |
| go_all_in_on_ace | 50 | 15.14% | 10.34% | +4.80 pp | 2.58% |
| raise_by_pot_when_biggest_stack | 44 | 15.93% | 10.23% | +5.70 pp | 2.68% |
| go_all_in_on_pair | 47 | 16.36% | 9.53% | +6.83 pp | 1.28% |

These are nine-player tournament associations. Eight opponents vary together, so the differences do not isolate individual head-to-head effects. Results can also reflect which other opponents share a lineup.

## Combined opponent presence

| Minimum-raise bot present | exploiter present | Batches | myAI win rate | Mean place |
|---|---|---:|---:|---:|
| No | No | 33 | 25.24% | 2.572 |
| Yes | No | 24 | 5.17% | 3.979 |
| No | Yes | 21 | 12.52% | 3.635 |
| Yes | Yes | 22 | 2.45% | 4.429 |

## Best five lineups

- Batch 30, 55.0% wins and mean place 1.96. Opponents: call_when_big_blind, call_when_blind, default, go_all_in, go_all_in_on_ace, go_all_in_on_pair, raise_by_half_of_stack, raise_by_pot.
- Batch 63, 54.0% wins and mean place 1.95. Opponents: call, call_preflop, default, go_all_in_on_ace, go_all_in_on_pair, raise_by_pot, raise_by_pot_when_biggest_stack, real_play_statistics.
- Batch 18, 45.0% wins and mean place 1.84. Opponents: call_when_big_blind, default, go_all_in, go_all_in_on_ace, go_all_in_on_pair, phil_hellmuth, raise_by_pot_when_biggest_stack, sklansky_and_malmuth.
- Batch 50, 43.0% wins and mean place 2.57. Opponents: call, call_when_blind, default, go_all_in_on_ace, go_all_in_on_pair, player_notes, raise_by_half_of_stack, raise_by_pot_when_biggest_stack.
- Batch 91, 40.0% wins and mean place 2.99. Opponents: call, call_when_big_blind, default, go_all_in_on_ace, go_all_in_on_pair, player_notes, raise_by_pot_when_biggest_stack, real_play_statistics.

## Worst five lineups

- Batch 32, 0.0% wins and mean place 4.45. Opponents: bill_chen, call, exploiter, go_all_in_on_ace, player_notes, raise_by_big_blind_unless_raised, raise_by_pot, real_play_statistics.
- Batch 44, 0.0% wins and mean place 4.43. Opponents: bill_chen, call_preflop, call_when_blind, default, go_all_in_on_ace, go_all_in_on_pair, raise_by_big_blind_unless_raised, real_play_statistics.
- Batch 48, 0.0% wins and mean place 4.19. Opponents: call_when_big_blind, exploiter, go_all_in_on_ace, player_notes, raise_by_big_blind_unless_raised, raise_by_half_of_stack, raise_by_pot_when_biggest_stack, sklansky_and_malmuth.
- Batch 78, 0.0% wins and mean place 3.20. Opponents: call_preflop, exploiter, go_all_in, raise_by_big_blind_unless_raised, raise_by_half_of_stack, raise_by_pot, raise_by_pot_when_biggest_stack, sklansky_and_malmuth.
- Batch 95, 0.0% wins and mean place 3.83. Opponents: bill_chen, call, go_all_in, go_all_in_on_pair, raise_by_big_blind_unless_raised, raise_by_half_of_stack, real_play_statistics, sklansky_and_malmuth.

## Limits of the printed results

- The output lists tournament averages. It does not show actual seats, button positions, action frequencies, per-hand profit, or individual opponent transfers. Positional weaknesses and the causes of losses cannot be measured from these logs.
- All completed outputs say matches continue until one bot owns every chip. Average final chips therefore largely repeats the tournament win-rate result.
- Interrupted attempts are excluded. The completed logs and CSV contain one result per numbered batch. The three logged interrupted lineups were rerun.
- Each raw output is in run_001.txt through run_100.txt. results.csv holds all bot results; opponent_stats.csv holds presence/absence comparisons.
