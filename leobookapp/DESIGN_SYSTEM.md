# LeoBook Design System v2.0

> **Dart SDK**: 3.8.1 · **Flutter**: ≥3.22 · **Font**: Inter (GoogleFonts) · **Updated**: 2026-03-14

---

## 1. Color Palette

All tokens in `lib/core/constants/app_colors.dart`.

| Token | Hex | Role | WCAG |
|---|---|---|---|
| `primary` | `#6C63FF` | Electric violet — CTAs, focus rings | 7.1:1 on `neutral900` (AAA) |
| `primaryLight` | `#9D97FF` | Hover / tint | — |
| `primaryDark` | `#4B44CC` | Pressed accent | — |
| `secondary` | `#00D4AA` | Emerald teal — success indicators | 6.8:1 on `neutral900` |
| `secondaryLight` | `#4DFFDB` | Secondary tint | — |
| `secondaryDark` | `#009E7E` | Secondary deep | — |
| `success` | `#22C55E` | Correct predictions | 4.9:1 on `neutral900` |
| `warning` | `#F59E0B` | Caution states | 3.1:1 (large text AA) |
| `error` / `liveRed` | `#EF4444` | Error / live match | 4.6:1 on `neutral900` |
| `neutral50–900` | scale | Backgrounds / surfaces / text | — |
| `glass` | `#1A2332` 60% | Frosted card fill (dark) | — |
| `glassBorder` | `#FFFFFF` 8% | Card border | — |
| `textPrimary` | `#F1F5F9` | Body text on dark | 15:1 (AAA) |
| `textSecondary` | `#94A3B8` | Hint / secondary | 5.9:1 (AA) |
| `textDisabled` | `#475569` | Disabled state | — |
| `divider` | `#1E293B` | Dividers | — |
| `surfaceCard` | `#111827` | Card background | — |
| `surfaceElevated` | `#1E293B` | Modal / elevated | — |

---

## 2. Typography Scale

All in `lib/core/theme/leo_typography.dart`. Font: **Inter** via `GoogleFonts.inter()`.

| Style | Size (sp) | Weight | Use case |
|---|---|---|---|
| `displayLarge` | 57 | 400 | Hero numbers |
| `displayMedium` | 45 | 400 | Section hero |
| `displaySmall` | 36 | 400 | Feature headings |
| `headlineLarge` | 32 | 700 | Page titles |
| `headlineMedium` | 28 | 700 | Section titles |
| `headlineSmall` | 24 | 700 | Card headlines |
| `titleLarge` | 22 | 700 | AppBar, dialog title |
| `titleMedium` | 16 | 600 | List tile title |
| `titleSmall` | 14 | 600 | Subtitle |
| `bodyLarge` | 16 | 400 | Primary body text |
| `bodyMedium` | 14 | 400 | Standard body |
| `bodySmall` | 12 | 400 | Caption, helper text |
| `labelLarge` | 14 | 600 | Button labels |
| `labelMedium` | 12 | 600 | Tags, field labels |
| `labelSmall` | 11 | 600 | Micro labels, badges |

---

## 3. Spacing Grid

Base unit: **4dp**. All in `lib/core/constants/spacing_constants.dart`.

| Token | dp | Semantic use |
|---|---|---|
| `xs` | 4 | Icon gaps, micro spacing |
| `sm` | 8 | Tight padding, row gaps |
| `md` | 12 | Input content padding |
| `lg` | 16 | Standard padding |
| `xl` | 20 | Section gaps |
| `xl2` | 24 | Button horizontal padding |
| `xl3` | 32 | Card vertical spacing |
| `xl4` | 48 | Touch targets |
| `xl5–xl8` | 64–128 | Page-level spacing |
| `cardPadding` | 16 | `GlassCard` default padding |
| `cardRadius` | 16 | Card border radius |
| `borderRadius` | 12 | Input / button radius |
| `chipRadius` | 100 | Pill / stadium |
| `componentGap` | 16 | Column gaps between components |
| `screenPadding` | 20 | Horizontal screen margins |
| `sectionGap` | 32 | Between page sections |
| `touchTarget` | 48 | Min tap area (WCAG 2.5.5) |
| `iconSize` | 24 | Standard icon |

---

## 4. Responsive Breakpoints

`lib/core/constants/responsive_constants.dart`

| DeviceType | Width | Behaviour |
|---|---|---|
| `mobile` | < 480dp | Single-column, compact |
| `tablet` | 480–767dp | Two-column, larger type |
| `desktop` | ≥ 1024dp | Sidebar nav, multi-column |

```dart
final type = Responsive.of(context); // → DeviceType
final fontSize = Responsive.sp(context, 14); // fluid, clamped 0.65×–1.6×
```

---

## 5. Component Gallery

### LeoButton — `shared/buttons/leo_button.dart`

| Param | Type | Default |
|---|---|---|
| `label` | `String` | required |
| `onPressed` | `VoidCallback?` | required (null = disabled) |
| `variant` | `LeoButtonVariant` | `primary` |
| `size` | `LeoButtonSize` | `medium` |
| `leadingIcon` | `Widget?` | null |
| `isLoading` | `bool` | false |
| `fullWidth` | `bool` | false |

```dart
LeoButton(label: 'View Prediction', onPressed: () {});
LeoButton(label: 'Filter', variant: LeoButtonVariant.secondary, isLoading: true, onPressed: null);
```

---

### GlassCard — `shared/cards/glass_card.dart`

```dart
GlassCard(
  onTap: () => openDetail(match),
  child: Column(children: [
    Text(match.homeTeam, style: LeoTypography.titleMedium),
    LeoBadge(label: 'LIVE', variant: LeoBadgeVariant.live),
  ]),
);
```

---

### LeoBadge — `shared/badges/leo_badge.dart`

| Variant | Colour | Use |
|---|---|---|
| `live` | Red tint + dot | Ongoing match |
| `finished` | Neutral | FT result |
| `scheduled` | Primary tint | Upcoming |
| `prediction` | Secondary tint | Leo prediction |
| `betPlaced` | Success tint | Placed bet |
| `custom` | Caller colours | Freeform |

```dart
LeoBadge(label: "LIVE 34'", variant: LeoBadgeVariant.live);
LeoBadge(label: 'FT', variant: LeoBadgeVariant.finished, size: LeoBadgeSize.small);
```

---

### LeoChip — `shared/chips/leo_chip.dart`

```dart
LeoChip(label: 'Premier League', selected: true, icon: Icons.sports_soccer, onDelete: clearFilter);
```

---

### LeoTextField — `shared/forms/leo_text_field.dart`

```dart
LeoTextField(
  label: 'Email', hint: 'you@example.com',
  keyboardType: TextInputType.emailAddress,
  validator: (v) => v!.contains('@') ? null : 'Invalid email',
);
```

---

### LeoSwitch / LeoCheckbox — `shared/toggles/`

```dart
// Theme toggle
LeoSwitch(
  value: context.watch<ThemeCubit>().isDark,
  onChanged: (_) => context.read<ThemeCubit>().toggleTheme(),
  semanticLabel: 'Toggle dark mode',
);
```

---

## 6. Animation Guidelines

`lib/core/animations/leo_animations.dart`

| Token | Value | Curve | Use case |
|---|---|---|---|
| `LeoDuration.micro` | 100ms | — | Immediate feedback |
| `LeoDuration.short` | 200ms | `smooth` | Press / border transitions |
| `LeoDuration.medium` | 300ms | `gentle` | Fade-in / slide-in |
| `LeoDuration.long` | 500ms | `gentle` | Pulse / shimmer |
| `LeoDuration.xlong` | 800ms | `bouncy` | Page hero entrance |
| `LeoCurve.smooth` | `easeInOutCubic` | — | General transitions |
| `LeoCurve.bouncy` | `easeOutBack` | — | Celebratory |
| `LeoCurve.sharp` | `easeOutExpo` | — | Dismiss / collapse |
| `LeoCurve.gentle` | `easeInOut` | — | Subtle bg animations |

**Stagger pattern:**
```dart
ListView.builder(
  itemBuilder: (ctx, i) => LeoFadeIn(
    delay: Duration(milliseconds: i * 50),
    child: MatchCard(match: matches[i]),
  ),
);
```

---

## 7. Accessibility Checklist

- [x] 7:1 contrast for all `textPrimary` on `neutral900` (AAA)
- [x] 4.5:1 minimum on all interactive elements
- [x] 48×48dp minimum touch targets (`LeoButton`, `LeoChip`)
- [x] `Semantics(button: true)` on all tappable widgets
- [x] `Semantics(toggled:)` on `LeoSwitch`
- [x] `Semantics(checked:)` on `LeoCheckbox`
- [x] `Semantics(label:)` on `MatchCard` (team + status)
- [x] Focus ring (2px `AppColors.primary`) on `LeoTextField`
- [x] Error messages exposed via `liveRegion: true`
- [ ] Team crest `CachedNetworkImage` — add `Semantics(image: true, label:)`
- [ ] Decorative icons — wrap with `ExcludeSemantics`

---

## 8. Migration Guide

```dart
// Color
Color(0xFF1E88E5)  →  AppColors.primary

// Spacing
EdgeInsets.all(16)  →  EdgeInsets.all(SpacingScale.lg)

// Typography
TextStyle(fontSize: 14, fontWeight: FontWeight.w600)  →  LeoTypography.labelLarge

// Card
Container(decoration: BoxDecoration(...))  →  GlassCard(child: ...)

// Button
ElevatedButton(onPressed: f, child: Text('X'))  →  LeoButton(label: 'X', onPressed: f)

// Theme toggle — in main.dart (already wired):
BlocProvider<ThemeCubit>(create: (_) => ThemeCubit())
// In widget:
LeoSwitch(value: context.watch<ThemeCubit>().isDark, onChanged: (_) => context.read<ThemeCubit>().toggleTheme())
```

---

## File Map

| File | Purpose |
|---|---|
| `core/constants/app_colors.dart` | Color tokens + legacy aliases |
| `core/theme/leo_typography.dart` | M3 type scale (Inter) |
| `core/constants/spacing_constants.dart` | 4dp grid + semantic aliases |
| `core/constants/responsive_constants.dart` | Breakpoints + Responsive helpers |
| `core/theme/app_theme_v2.dart` | Dark + Light ThemeData |
| `core/theme/theme_cubit.dart` | ThemeMode Cubit |
| `core/animations/leo_animations.dart` | Duration/Curve tokens + widgets |
| `shared/buttons/leo_button.dart` | Primary button |
| `shared/cards/glass_card.dart` | Glass surface card |
| `shared/badges/leo_badge.dart` | Status badge |
| `shared/chips/leo_chip.dart` | Filter chip |
| `shared/forms/leo_text_field.dart` | Animated input |
| `shared/toggles/leo_switch.dart` | Toggle switch |
| `shared/toggles/leo_checkbox.dart` | Checkbox |

*Last updated: 2026-03-14 — LeoBook Engineering / Materialless LLC*
