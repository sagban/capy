# Seed inventory (content only)

Import code is Phase 1 (#32). This list is the Phase 0 content draft.

## Foods (~30)

IDs are stable seed keys. Macros are per 100 g (approx; refine from USDA when importing).

| id | name | family | cal | P | C | F | notes |
|----|------|--------|-----|---|---|---|-------|
| seed_chicken_breast | Chicken breast, cooked | poultry | 165 | 31 | 0 | 3.6 | |
| seed_eggs | Egg, whole | egg | 143 | 13 | 0.7 | 9.5 | |
| seed_egg_whites | Egg white | egg | 52 | 11 | 0.7 | 0.2 | |
| seed_salmon | Salmon, cooked | fish | 206 | 22 | 0 | 12 | |
| seed_greek_yogurt | Greek yogurt, plain | dairy | 97 | 9 | 3.6 | 5 | |
| seed_milk_2pct | Milk 2% | dairy | 50 | 3.3 | 4.8 | 2 | |
| seed_cheddar | Cheddar cheese | dairy | 403 | 25 | 1.3 | 33 | |
| seed_paneer | Paneer | dairy | 265 | 18 | 1.2 | 20 | |
| seed_tofu_firm | Tofu, firm | soy | 144 | 17 | 3 | 9 | |
| seed_white_rice_cooked | White rice, cooked | grain | 130 | 2.7 | 28 | 0.3 | |
| seed_brown_rice_cooked | Brown rice, cooked | grain | 123 | 2.7 | 26 | 0.9 | |
| seed_roti | Roti / chapati | grain | 297 | 9 | 46 | 7.5 | composite-friendly |
| seed_oats | Oats, dry | grain | 389 | 17 | 66 | 7 | |
| seed_bread_wheat | Whole wheat bread | grain | 247 | 13 | 41 | 3.4 | |
| seed_potato_boiled | Potato, boiled | starch | 87 | 1.9 | 20 | 0.1 | |
| seed_sweet_potato | Sweet potato, baked | starch | 90 | 2 | 21 | 0.2 | |
| seed_banana | Banana | fruit | 89 | 1.1 | 23 | 0.3 | |
| seed_apple | Apple | fruit | 52 | 0.3 | 14 | 0.2 | |
| seed_broccoli | Broccoli, cooked | veg | 35 | 2.4 | 7 | 0.4 | |
| seed_spinach | Spinach, cooked | veg | 23 | 3 | 3.8 | 0.3 | |
| seed_tomato | Tomato | veg | 18 | 0.9 | 3.9 | 0.2 | |
| seed_onion | Onion | veg | 40 | 1.1 | 9 | 0.1 | |
| seed_avocado | Avocado | fat | 160 | 2 | 8.5 | 15 | |
| seed_olive_oil | Olive oil | fat | 884 | 0 | 0 | 100 | |
| seed_almonds | Almonds | nut | 579 | 21 | 22 | 50 | |
| seed_peanut_butter | Peanut butter | nut | 588 | 25 | 20 | 50 | |
| seed_black_beans | Black beans, cooked | legume | 132 | 8.9 | 24 | 0.5 | |
| seed_chickpeas | Chickpeas, cooked | legume | 164 | 8.9 | 27 | 2.6 | |
| seed_dal_cooked | Dal (cooked lentils) | legume | 116 | 9 | 20 | 0.4 | base for composites |
| seed_protein_powder | Whey protein powder | supplement | 400 | 80 | 10 | 3 | per 100g powder |

## Manual Indian / mixed composites

| id | name | components (food_id × g per serving) |
|----|------|----------------------------------------|
| seed_dal_tadka_bowl | Dal tadka bowl | seed_dal_cooked×200, seed_onion×30, seed_tomato×40, seed_olive_oil×5 |
| seed_paneer_bhurji | Paneer bhurji | seed_paneer×120, seed_onion×40, seed_tomato×40, seed_olive_oil×8 |
| seed_chicken_stirfry | Chicken stir-fry | seed_chicken_breast×150, seed_broccoli×100, seed_onion×40, seed_olive_oil×8 |
| seed_yogurt_rice | Curd rice | seed_greek_yogurt×150, seed_white_rice_cooked×150 |
| seed_roti_dal_plate | Roti + dal plate | seed_roti×80, seed_dal_cooked×180 |

Mark `isComposite=true`. Macros = sum of component per100g × grams / 100. **LLM must not invent composite macros.**

## Meal templates (suggestion corpus)

| id | name | items |
|----|------|-------|
| tpl_chicken_stirfry | Chicken stir-fry | seed_chicken_stirfry × 1 serving |
| tpl_greek_yogurt_bowl | Yogurt + banana + almonds | yogurt 200g, banana 100g, almonds 15g |
| tpl_salmon_rice | Salmon + rice + broccoli | salmon 150g, rice 180g, broccoli 100g |
| tpl_tofu_bowl | Tofu bowl | tofu 150g, rice 150g, broccoli 100g, oil 5g |
| tpl_dal_roti | Dal + roti | seed_roti_dal_plate |
| tpl_paneer_bhurji_roti | Paneer bhurji + roti | paneer bhurji + roti 40g |
| tpl_oats_protein | Oats + protein | oats 60g, protein powder 30g, milk 200g |
| tpl_egg_whites_toast | Egg whites + toast | egg whites 200g, bread 60g |
| tpl_chickpea_salad | Chickpea salad | chickpeas 200g, tomato 100g, onion 40g, oil 8g |
| tpl_sweet_potato_chicken | Sweet potato + chicken | chicken 150g, sweet potato 200g |
| tpl_peanut_banana | Snack: PB banana | banana 100g, peanut butter 20g |
| tpl_curd_rice | Curd rice | seed_yogurt_rice |

## Aliases (examples)

- “chipotle chicken” → map via search later; not in seed
- “curd” → seed_greek_yogurt (approx) or dedicated dahi entry later
- “chapati” → seed_roti
