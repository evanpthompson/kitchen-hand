import 'dart:convert';
import 'package:http/http.dart' as http;

/// Thin wrapper over the Kitchen Hand ingestion backend (service/).
/// The backend is the source of truth for validation/dedup; this client
/// does no business logic of its own, just HTTP + JSON plumbing.
class ApiClient {
  ApiClient({this.baseUrl = 'http://127.0.0.1:8000'});

  String baseUrl;

  Uri _uri(String path, [Map<String, String>? query]) =>
      Uri.parse('$baseUrl$path').replace(queryParameters: query);

  Future<dynamic> _get(String path) async {
    final res = await http.get(_uri(path));
    _checkOk(res);
    return jsonDecode(res.body);
  }

  Future<dynamic> _put(String path, Map<String, dynamic> body) async {
    final res = await http.put(
      _uri(path),
      headers: {'content-type': 'application/json'},
      body: jsonEncode(body),
    );
    _checkOk(res);
    return jsonDecode(res.body);
  }

  Future<dynamic> _post(
    String path, {
    Map<String, String>? query,
    Map<String, dynamic>? body,
  }) async {
    final res = await http.post(
      _uri(path, query),
      headers: body != null ? {'content-type': 'application/json'} : null,
      body: body != null ? jsonEncode(body) : null,
    );
    _checkOk(res);
    return jsonDecode(res.body);
  }

  Future<dynamic> _delete(String path) async {
    final res = await http.delete(_uri(path));
    _checkOk(res);
    return jsonDecode(res.body);
  }

  void _checkOk(http.Response res) {
    if (res.statusCode >= 200 && res.statusCode < 300) return;
    // FastAPI error bodies are JSON with a "detail" key (string or object).
    String detail = res.body;
    try {
      final decoded = jsonDecode(res.body);
      if (decoded is Map && decoded.containsKey('detail')) {
        detail = decoded['detail'] is String
            ? decoded['detail']
            : jsonEncode(decoded['detail']);
      }
    } catch (_) {
      // leave detail as raw body
    }
    throw ApiException(res.statusCode, detail);
  }

  // --- Inbox ---

  Future<List<dynamic>> listInbox() => _get('/inbox').then((v) => v as List);

  Future<Map<String, dynamic>> getInboxCapture(String slug) =>
      _get('/inbox/$slug').then((v) => v as Map<String, dynamic>);

  String inboxFileUrl(String slug, String filename) =>
      '$baseUrl/inbox/$slug/files/$filename';

  Future<Map<String, dynamic>> captureYoutube(String slug, String url) =>
      _post('/inbox/$slug/youtube', body: {'url': url})
          .then((v) => v as Map<String, dynamic>);

  // --- Drafts ---

  Future<List<dynamic>> listDrafts() => _get('/drafts').then((v) => v as List);

  Future<Map<String, dynamic>> getDraft(String slug) =>
      _get('/drafts/$slug').then((v) => v as Map<String, dynamic>);

  Future<Map<String, dynamic>> saveDraft(
    String slug,
    Map<String, dynamic> data,
  ) => _put('/drafts/$slug', data).then((v) => v as Map<String, dynamic>);

  Future<Map<String, dynamic>> validateDraft(String slug) =>
      _post('/drafts/$slug/validate').then((v) => v as Map<String, dynamic>);

  Future<Map<String, dynamic>> promoteDraft(
    String slug, {
    bool force = false,
  }) => _post(
    '/drafts/$slug/promote',
    query: force ? {'force': 'true'} : null,
  ).then((v) => v as Map<String, dynamic>);

  Future<void> discardDraft(String slug) => _delete('/drafts/$slug');

  // --- Recipes ---

  Future<List<dynamic>> listRecipes() =>
      _get('/recipes').then((v) => v as List);

  Future<Map<String, dynamic>> getRecipe(String slug) =>
      _get('/recipes/$slug').then((v) => v as Map<String, dynamic>);

  Future<List<dynamic>> listTags() =>
      _get('/recipes/tags').then((v) => v as List);
}

class ApiException implements Exception {
  ApiException(this.statusCode, this.detail);
  final int statusCode;
  final String detail;

  @override
  String toString() => 'ApiException($statusCode): $detail';
}
