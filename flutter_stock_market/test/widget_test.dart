import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_stock_market/main.dart';

void main() {
  testWidgets('StockResearchApp smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const ProviderScope(child: StockResearchApp()));
    expect(find.text('Stock Market AI'), findsOneWidget);
  });
}
