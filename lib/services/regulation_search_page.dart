import 'package:flutter/material.dart';

import '../app/backend_status_banner.dart';
import '../app/backend_status_controller.dart';
import '../features/ai_assistant/data/remote/assistant_api_client.dart';
import '../features/ai_assistant/data/repositories/assistant_repository.dart';
import '../features/ai_assistant/domain/models/regulation_source.dart';
import '../features/ai_assistant/presentation/assistant_error_messages.dart';

class RegulationSearchPage extends StatefulWidget {
  final bool isArabic;
  final String? initialQuery;
  final Future<void> Function()? onSessionExpired;

  const RegulationSearchPage({
    super.key,
    required this.isArabic,
    this.initialQuery,
    this.onSessionExpired,
  });

  @override
  State<RegulationSearchPage> createState() => _RegulationSearchPageState();
}

class _RegulationSearchPageState extends State<RegulationSearchPage> {
  final TextEditingController _controller = TextEditingController();
  final AssistantRepository _assistantRepository = const AssistantRepository();
  bool _isLoading = false;
  bool _hasSearched = false;
  List<RegulationSource> _results = const [];

  @override
  void initState() {
    super.initState();
    final query = widget.initialQuery?.trim();
    if (query != null && query.isNotEmpty) {
      _controller.text = query;
    }
  }

  bool get _isBackendOffline =>
      BackendStatusController.instance.snapshot.isOffline;

  String get _backendUnavailableMessage => widget.isArabic
      ? 'الخادم غير متاح حالياً. شغّل الـ backend المحلي ثم حدّث الحالة من البطاقة أدناه.'
      : 'The backend is currently unavailable. Start the local backend, then refresh the status below.';

  void _showBackendUnavailableSnackBar() {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(_backendUnavailableMessage)));
  }

  bool _isSessionError(AssistantApiException error) {
    return error.kind == AssistantApiErrorKind.authenticationRequired ||
        error.kind == AssistantApiErrorKind.sessionExpired ||
        error.kind == AssistantApiErrorKind.unauthorized;
  }

  bool _shouldRefreshBackendIndicator(AssistantApiException error) {
    return error.kind == AssistantApiErrorKind.network ||
        error.kind == AssistantApiErrorKind.timeout ||
        error.kind == AssistantApiErrorKind.invalidResponse;
  }

  Future<void> _search() async {
    final query = _controller.text.trim();
    if (_isLoading) return;
    if (query.isEmpty) {
      setState(() {
        _results = const [];
        _hasSearched = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            widget.isArabic
                ? 'أدخل عبارة للبحث في المصادر الرسمية.'
                : 'Enter a query to search the official sources.',
          ),
        ),
      );
      return;
    }

    if (_isBackendOffline) {
      _showBackendUnavailableSnackBar();
      return;
    }

    setState(() => _isLoading = true);
    try {
      final response = await _assistantRepository.searchRegulations(query);
      if (!mounted) return;
      setState(() {
        _results = response;
        _hasSearched = true;
        _isLoading = false;
      });
    } on AssistantApiException catch (error) {
      if (!mounted) return;

      setState(() {
        _results = const [];
        _isLoading = false;
        _hasSearched = true;
      });

      if (_isSessionError(error)) {
        final navigator = Navigator.of(context);
        if (navigator.canPop()) {
          navigator.pop();
        }
        await widget.onSessionExpired?.call();
        return;
      }
      if (_shouldRefreshBackendIndicator(error)) {
        BackendStatusController.instance.refresh(showCheckingState: false);
      }

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            localizeAssistantError(
              error,
              isArabic: widget.isArabic,
              action: AssistantRequestAction.search,
            ),
          ),
        ),
      );
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _results = const [];
        _isLoading = false;
        _hasSearched = true;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            localizeUnexpectedAssistantError(
              isArabic: widget.isArabic,
              action: AssistantRequestAction.search,
            ),
          ),
        ),
      );
    }
  }

  void _showResult(RegulationSource reference) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => SafeArea(
        top: false,
        child: Container(
          decoration: const BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
          ),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Center(
                    child: Container(
                      width: 42,
                      height: 4,
                      decoration: BoxDecoration(
                        color: Colors.grey.shade300,
                        borderRadius: BorderRadius.circular(999),
                      ),
                    ),
                  ),
                  const SizedBox(height: 18),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: const Color(0xFF5421D9).withValues(alpha: 0.08),
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: Text(
                      reference.sourceTypeTag(isArabic: widget.isArabic),
                      style: const TextStyle(
                        color: Color(0xFF5421D9),
                        fontWeight: FontWeight.w800,
                        fontSize: 12.5,
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),
                  Text(
                    reference.primaryDisplayTitle,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                      height: 1.35,
                    ),
                  ),
                  if (reference.secondaryDisplayArticle.isNotEmpty) ...[
                    const SizedBox(height: 10),
                    Text(
                      reference.secondaryDisplayArticle,
                      style: TextStyle(color: Colors.grey[700], height: 1.45),
                    ),
                  ],
                  if (reference.secondaryDisplaySection.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Text(
                      reference.secondaryDisplaySection,
                      style: TextStyle(
                        color: Colors.grey[600],
                        fontSize: 13.5,
                        height: 1.4,
                      ),
                    ),
                  ],
                  const SizedBox(height: 18),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF7F8FC),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: Colors.grey.shade300),
                    ),
                    child: Text(
                      reference.content.isNotEmpty
                          ? reference.content
                          : reference.contentPreview,
                      style: const TextStyle(fontSize: 15, height: 1.6),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF7F8FC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        title: Text(
          widget.isArabic
              ? 'البحث في المصادر الرسمية'
              : 'Official Sources Search',
          style: const TextStyle(fontWeight: FontWeight.w800),
        ),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(18),
                boxShadow: const [
                  BoxShadow(
                    color: Color(0x0F000000),
                    blurRadius: 10,
                    offset: Offset(0, 4),
                  ),
                ],
              ),
              child: Column(
                children: [
                  AnimatedBuilder(
                    animation: BackendStatusController.instance,
                    builder: (context, _) {
                      final isBackendOffline =
                          BackendStatusController.instance.snapshot.isOffline;
                      final canSearch = !_isLoading && !isBackendOffline;

                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Row(
                            children: [
                              Expanded(
                                child: TextField(
                                  controller: _controller,
                                  textAlign: widget.isArabic
                                      ? TextAlign.right
                                      : TextAlign.left,
                                  decoration: InputDecoration(
                                    hintText: widget.isArabic
                                        ? 'ابحث في المصادر الرسمية...'
                                        : 'Search official sources...',
                                    filled: true,
                                    fillColor: const Color(0xFFF7F8FC),
                                    border: OutlineInputBorder(
                                      borderRadius: BorderRadius.circular(14),
                                      borderSide: BorderSide.none,
                                    ),
                                    contentPadding: const EdgeInsets.symmetric(
                                      horizontal: 16,
                                      vertical: 14,
                                    ),
                                  ),
                                  onSubmitted: canSearch
                                      ? (_) => _search()
                                      : null,
                                ),
                              ),
                              const SizedBox(width: 10),
                              ElevatedButton(
                                onPressed: canSearch ? _search : null,
                                style: ElevatedButton.styleFrom(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 18,
                                    vertical: 15,
                                  ),
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(14),
                                  ),
                                ),
                                child: Text(widget.isArabic ? 'بحث' : 'Search'),
                              ),
                            ],
                          ),
                          if (isBackendOffline) ...[
                            const SizedBox(height: 10),
                            Text(
                              _backendUnavailableMessage,
                              textAlign: TextAlign.center,
                              style: const TextStyle(
                                color: Color(0xFF7F1D1D),
                                fontSize: 12.5,
                                fontWeight: FontWeight.w600,
                                height: 1.4,
                              ),
                            ),
                          ],
                        ],
                      );
                    },
                  ),
                  const SizedBox(height: 12),
                  BackendStatusBanner(isArabic: widget.isArabic),
                ],
              ),
            ),
          ),
          if (_isLoading) const LinearProgressIndicator(),
          Expanded(
            child: _results.isEmpty
                ? Center(
                    child: Text(
                      _hasSearched
                          ? (widget.isArabic
                                ? 'لم أجد نتائج مطابقة في المصادر الرسمية.'
                                : 'No matching official source results were found.')
                          : (widget.isArabic
                                ? 'أدخل عبارة للبحث في المصادر الرسمية.'
                                : 'Enter a query to search the official sources.'),
                      textAlign: TextAlign.center,
                      style: const TextStyle(height: 1.5, fontSize: 14.5),
                    ),
                  )
                : ListView.separated(
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                    itemCount: _results.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 10),
                    itemBuilder: (context, index) {
                      final result = _results[index];
                      return Card(
                        elevation: 0,
                        color: Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                          side: BorderSide(color: Colors.grey.shade200),
                        ),
                        child: ListTile(
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 10,
                          ),
                          title: Text(
                            '${result.sourceTypeTag(isArabic: widget.isArabic)} ${result.primaryDisplayTitle}',
                            style: const TextStyle(
                              fontWeight: FontWeight.w800,
                              height: 1.35,
                            ),
                          ),
                          subtitle: Text(
                            [
                              if (result.secondaryDisplayArticle.isNotEmpty)
                                result.secondaryDisplayArticle,
                              if (result.secondaryDisplaySection.isNotEmpty)
                                result.secondaryDisplaySection,
                              if (result.contentPreview.isNotEmpty)
                                result.contentPreview,
                            ].join('\n'),
                            maxLines: 5,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(height: 1.5),
                          ),
                          onTap: () => _showResult(result),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }
}
