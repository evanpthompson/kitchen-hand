import 'package:flutter/material.dart';
import 'api/api_client.dart';
import 'screens/drafts_screen.dart';
import 'screens/inbox_screen.dart';
import 'screens/recipes_screen.dart';

void main() {
  runApp(const KitchenHandApp());
}

class KitchenHandApp extends StatelessWidget {
  const KitchenHandApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Kitchen Hand',
      theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepOrange)),
      home: const HomeShell(),
    );
  }
}

/// Navigation shell across the three v1 screens (docs/app-spec.md):
/// inbox queue, draft review, collection browser. Desktop-first, hence
/// NavigationRail rather than a bottom nav bar.
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  final ApiClient _api = ApiClient();
  int _index = 0;

  Future<void> _editBackendUrl() async {
    final controller = TextEditingController(text: _api.baseUrl);
    final result = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Backend URL'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(hintText: 'http://127.0.0.1:8000'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(controller.text),
            child: const Text('Save'),
          ),
        ],
      ),
    );
    if (result != null && result.isNotEmpty) {
      setState(() => _api.baseUrl = result);
    }
  }

  @override
  Widget build(BuildContext context) {
    final screens = [
      InboxScreen(api: _api, key: ValueKey('inbox-${_api.baseUrl}')),
      DraftsScreen(api: _api, key: ValueKey('drafts-${_api.baseUrl}')),
      RecipesScreen(api: _api, key: ValueKey('recipes-${_api.baseUrl}')),
    ];

    return Scaffold(
      body: Row(
        children: [
          NavigationRail(
            selectedIndex: _index,
            onDestinationSelected: (i) => setState(() => _index = i),
            labelType: NavigationRailLabelType.all,
            leading: Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: IconButton(
                onPressed: _editBackendUrl,
                icon: const Icon(Icons.settings),
                tooltip: 'Backend URL: ${_api.baseUrl}',
              ),
            ),
            destinations: const [
              NavigationRailDestination(
                icon: Icon(Icons.inbox_outlined),
                selectedIcon: Icon(Icons.inbox),
                label: Text('Inbox'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.edit_note_outlined),
                selectedIcon: Icon(Icons.edit_note),
                label: Text('Drafts'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.menu_book_outlined),
                selectedIcon: Icon(Icons.menu_book),
                label: Text('Recipes'),
              ),
            ],
          ),
          const VerticalDivider(width: 1),
          Expanded(child: screens[_index]),
        ],
      ),
    );
  }
}
