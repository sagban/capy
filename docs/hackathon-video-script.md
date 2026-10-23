# Capy

Capy is a food log you talk to. You say what you want to eat. Capy finds a meal that still fits today, and that you will actually eat. The log fills in after that.

## The awareness gap

People want to stay healthy. They need a clear picture of the day. Logging food is part of that. Most apps make logging harder than the meal. A search box. A barcode. A meal plan that is gone in a week. You miss a day, and it feels like you failed.

## What the tracker makes you do

What can I eat right now, with what I have left? That is the real question. A tracker gives you a form. You stop, look up each food, guess the portion, and hope the number is right. If you only ate half, there is nothing real to change.

## What it does

You say the meal, or you ask what fits. Capy looks the food up, turns your portion into grams, and writes one line. The calories and macros come from that food. Capy tells you what it logged, and what you have left.

## A meal is three tool calls

Logging a meal takes three steps. Capy cannot skip one and make the plate up. It finds the food. It turns your portion into grams, using that food’s own measures. Then it writes one line. The numbers for 100 grams are copied from the food. The log does the math. If you only ate half, Capy opens today and changes that one line.

## One diary. Two doors.

When your hands are busy, you say the meal to Alexa+. It uses the same tools, through MCP. If you are not signed in, nothing is logged. On the phone, Capy waits until you confirm the food, the grams, and the numbers. The model can talk. It cannot make up the meal.

## Capy on AWS

Alexa+ and the phone share one log. API Gateway is the front door. App Runner runs the server and writes the meal while you are talking. Lambda runs the phone and waits for you to confirm. Bedrock is the model. DynamoDB stores the log. Cognito signs you in. The USDA key stays in Secrets Manager.

## Architecture

The meal comes in through the gateway. The tools find the food, turn the portion into grams, and write the line. The phone shows the same log.

## Demo

Two large eggs and a cup of rice.

That is what got logged, and this is what you have left.

I only ate half.

Same day. That one line changed.

The phone is the same log.

## Close

You eat. The log is already written.
