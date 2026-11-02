/// Request policy, shared by the search selector and backend request.
enum RankingMode {
  bestOverall(
    'best_overall',
    'Best overall',
    'Balance parking cost, walking distance, availability and driving time.',
  ),
  cheaper(
    'cheaper',
    'Prioritise cheaper',
    'Give more weight to lower parking cost for your full stay.',
  ),
  closer(
    'closer',
    'Prioritise closer',
    'Give more weight to a shorter walk from the carpark to your destination.',
  );

  final String apiValue;
  final String label;
  final String description;

  const RankingMode(this.apiValue, this.label, this.description);
}
