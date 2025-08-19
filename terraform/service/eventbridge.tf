module "eventbridge" {
  # source  = "terraform-aws-modules/eventbridge/aws"
  # version = "4.1.0"

  # Pin to a git commit instead. This is the same as the above.
  source = "git::https://github.com/terraform-aws-modules/terraform-aws-eventbridge.git?ref=3e8657cd925d5b4a21301a09b67d8081f24bcfc3"

  role_name = "${var.lambda_name}-eventbridge-role"

  create_bus = false

  rules = {
    "${var.lambda_name}-crons" = {
      description         = "Trigger for ${var.lambda_name} Function"
      schedule_expression = var.schedule
    }
  }

  targets = {
    "${var.lambda_name}-crons" = [
      {
        name  = "${var.lambda_name}-function-cron"
        arn   = aws_lambda_function.lambda_function.arn
        input = jsonencode({})
      }
    ]
  }
}

resource "aws_lambda_permission" "allow_eventbridge_to_invoke_lambda" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda_function.arn
  principal     = "events.amazonaws.com"
  source_arn    = module.eventbridge.eventbridge_rules["${var.lambda_name}-crons"]["arn"]
}