#!/bin/bash
#set

cat << EOF > "${1-athenarunner-event.json}"
{
  "version": "0",
  "id": "1234abcd-ab12-123a-123a-1234567890ab",
  "detail-type": "Trusted Advisor Check Item Refresh Notification",
  "source": "aws.trustedadvisor",
  "account": "123456789012",
  "time": "2021-04-05T20:07:49Z",
  "region": "eu-west-2",
  "resources": [],
  "detail": {
    "check-name": "Some Fake Event",
    "status": "WARN",
    "resource_id": "arn:aws:ec2:eu-west-2-1:123456789012:instance/i-01234567890abcdef",
    "uuid": "aa12345f-55c7-498e-b7ac-123456789012"
  }
}
EOF