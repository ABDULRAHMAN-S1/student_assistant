import 'package:flutter/material.dart';

import 'ai_api.dart';

class RegulationSearchPage extends StatefulWidget {
  final bool isArabic;

  const RegulationSearchPage({super.key, required this.isArabic});

  @override
  State<RegulationSearchPage> createState() => _RegulationSearchPageState();
}

class _RegulationSearchPageState extends State<RegulationSearchPage> {
  final TextEditingController _controller = TextEditingController();
  bool _isLoading = false;
  List<AiSourceReference> _results = const [];

  Future<void> _search() async {
    final query = _controller.text.trim();
    if (query.isEmpty || _isLoading) return;

    setState(() => _isLoading = true);
    try {
      final response = await AiApi.searchRegulations(query);
      if (!mounted) return;
      setState(() {
        _results = response.results;
        _isLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            widget.isArabic
                ? 'تعذر تنفيذ البحث الآن.'
                : 'Could not complete the search right now.',
          ),
        ),
      );
    }
  }

  void _showResult(AiSourceReference reference) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  reference.article.isNotEmpty
                      ? reference.article
                      : (reference.title.isNotEmpty
                            ? reference.title
                            : reference.documentTitle),
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                if (reference.section.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(
                    reference.section,
                    style: TextStyle(color: Colors.grey[700]),
                  ),
                ],
                if (reference.documentTitle.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(
                    reference.documentTitle,
                    style: TextStyle(color: Colors.grey[600]),
                  ),
                ],
                const SizedBox(height: 16),
                Text(
                  reference.content.isNotEmpty
                      ? reference.content
                      : reference.contentPreview,
                  style: const TextStyle(fontSize: 15, height: 1.5),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.isArabic ? 'البحث في اللوائح' : 'Regulation Search'),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    textAlign: widget.isArabic
                        ? TextAlign.right
                        : TextAlign.left,
                    decoration: InputDecoration(
                      hintText: widget.isArabic
                          ? 'ابحث في اللوائح...'
                          : 'Search regulations...',
                      border: const OutlineInputBorder(),
                    ),
                    onSubmitted: (_) => _search(),
                  ),
                ),
                const SizedBox(width: 8),
                ElevatedButton(
                  onPressed: _isLoading ? null : _search,
                  child: Text(widget.isArabic ? 'بحث' : 'Search'),
                ),
              ],
            ),
          ),
          if (_isLoading) const LinearProgressIndicator(),
          Expanded(
            child: _results.isEmpty
                ? Center(
                    child: Text(
                      widget.isArabic
                          ? 'أدخل عبارة للبحث في اللوائح.'
                          : 'Enter a query to search the regulations.',
                    ),
                  )
                : ListView.separated(
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                    itemCount: _results.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 10),
                    itemBuilder: (context, index) {
                      final result = _results[index];
                      return Card(
                        child: ListTile(
                          title: Text(
                            result.article.isNotEmpty
                                ? result.article
                                : (result.title.isNotEmpty
                                      ? result.title
                                      : result.documentTitle),
                          ),
                          subtitle: Text(
                            [
                              if (result.section.isNotEmpty) result.section,
                              if (result.contentPreview.isNotEmpty)
                                result.contentPreview,
                            ].join('\n'),
                            maxLines: 5,
                            overflow: TextOverflow.ellipsis,
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
