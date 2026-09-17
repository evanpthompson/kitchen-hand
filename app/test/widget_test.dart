import 'package:flutter_test/flutter_test.dart';

import 'package:kitchen_hand/main.dart';

void main() {
  testWidgets('shows navigation for all four screens', (tester) async {
    await tester.pumpWidget(const KitchenHandApp());
    await tester.pump();

    expect(find.text('Capture'), findsWidgets);
    expect(find.text('Inbox'), findsWidgets);
    expect(find.text('Drafts'), findsWidgets);
    expect(find.text('Recipes'), findsWidgets);
  });
}
