import '../../domain/models/assistant_reply.dart';
import '../../domain/models/regulation_source.dart';
import '../remote/assistant_api_client.dart';

class AssistantRepository {
  const AssistantRepository({AssistantApiClient? apiClient})
    : _apiClient = apiClient ?? const AssistantApiClient();

  final AssistantApiClient _apiClient;

  Future<AssistantReply> ask(String message) {
    return _apiClient.ask(message);
  }

  Future<List<RegulationSource>> searchRegulations(
    String query, {
    int topK = 6,
  }) {
    return _apiClient.searchRegulations(query, topK: topK);
  }

  Future<void> sendFeedback({
    required String question,
    required String answer,
    required bool helpful,
    required String language,
    required List<RegulationSource> sources,
  }) {
    return _apiClient.sendFeedback(
      question: question,
      answer: answer,
      helpful: helpful,
      language: language,
      sources: sources,
    );
  }
}
