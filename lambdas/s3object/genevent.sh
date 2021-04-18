#!/bin/bash
#set

cat << EOF > "${1-s3object-event.json}"
{
	"Records": [
		{
			"eventVersion": "2.1",
			"eventSource": "aws:s3",
			"awsRegion": "eu-west-1",
			"eventTime": "2021-04-11T15:04:23.473Z",
			"eventName": "ObjectCreated:Put",
			"userIdentity": {
				"principalId": "AWS:AIDA4H5SWEAPJATCAYKJK"
			},
			"requestParameters": {
				"sourceIPAddress": "46.233.116.242"
			},
			"responseElements": {
				"x-amz-request-id": "BC4DD33287351C20",
				"x-amz-id-2": "/S2XbXHr5ynjCNy2f4pWkAyxSqWBCjcvVLl3+JoKgA9TnsyRyGN9/ygB6X1N2lqqSWPe6Zes2ns="
			},
			"s3": {
				"s3SchemaVersion": "1.0",
				"configurationId": "dd56e4ae-1b0a-4dbc-86cc-99e7b4d580da",
				"bucket": {
					"name": "aws-test-data-bucket-070420212230\n",
					"ownerIdentity": {
						"principalId": "A3GF652PIWJM0B"
					},
					"arn": "arn:aws:s3:::dlg-data-platform-dev"
				},
				"object": {
					"key": "openaq/2020/02/01/openaq.csv",
					"size": 32907,
					"eTag": "ce44503030055f73da0e8604eb0e2052",
					"sequencer": "005D5C0BF758AC2FEC"
				}
			}
		}
	]
}
EOF