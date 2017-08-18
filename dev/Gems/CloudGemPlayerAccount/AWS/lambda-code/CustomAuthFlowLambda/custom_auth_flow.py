#
# All or portions of this file Copyright (c) Amazon.com, Inc. or its affiliates or
# its licensors.
#
# For complete copyright and license terms please see the LICENSE at the root of this
# distribution (the "License"). All use of this software is governed by the License,
# or, if provided, by the license below or the license accompanying this file. Do not
# remove or modify any license notices. This file is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#

import account_utils
import errors
import json
import traceback
import uuid

# Implements a custom authentication workflow.  Handles events generated by the lambda triggers on Cognito user pools.
# Documentation for Cognito custom authentication flow: http://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-authentication-flow.html
#
# This custom auth flow has four lambda invocations:
# 1. A DefineAuthChallenge_Authentication invocation to determine the next step.
#    The response is to send a custom challenge to the user.
# 2. A CreateAuthChallenge_Authentication invocation to set up the parameters for the custom challenge.
# 3. A VerifyAuthChallengeResponse_Authentication invocation to check if the user's response is correct.
# 4. A DefineAuthChallenge_Authentication invocation to determine the next step.
#    If the user's answer was correct, the response is to issue tokens to the user, which completes the custom auth flow.
#    If the user's answer was not correct, the response is that the auth flow has failed.
def dispatch(event, context):
    try:
        user_status = event.get('request', {}).get('userAttributes', {}).get('cognito:user_status', None)
        print 'Request Type: {}, Username: {}, Pool: {}, User Status: {}'.format(event['triggerSource'], event['userName'], event['userPoolId'], user_status)
        if event['triggerSource'] == 'DefineAuthChallenge_Authentication':
            define_auth_challenge(event)
        elif event['triggerSource'] == 'CreateAuthChallenge_Authentication':
            create_auth_challenge(event)
        elif event['triggerSource'] == 'VerifyAuthChallengeResponse_Authentication':
            verify_auth_challenge_response(event)
        else:
            raise RuntimeError('Unsupported event type {}'.format(event['triggerSource']))
        print 'Response: {}'.format(event['response'])
        return event
    except errors.ClientError:
        raise
    except:
        # Log exceptions and return a generic message instead to avoid leaking information.
        traceback.print_exc()
        raise RuntimeError('Internal Server Error')

# Decides the next step of the custom workflow.
# Custom workflows have one challenge that requires the user's password.
def define_auth_challenge(event):
    for challenge in event['request']['session']:
        if challenge['challengeName'] == 'CUSTOM_CHALLENGE' and (challenge['challengeMetadata'] == 'BasicAuth' or challenge['challengeMetadata'] == 'ForceChangePassword'):
            if challenge['challengeResult'] == True:
                # The user has successfully completed the challenge.
                # This response tells Cognito that the whole auth flow has succeeded.
                event['response']['issueTokens'] = True
                print 'Challenge {} complete, issuing tokens.'.format(challenge['challengeMetadata'])
                return
            else:
                # The user has failed the challenge.
                # This response tells Cognito that the whole auth flow has failed.
                event['response']['failAuthentication'] = True
                print 'Challenge {} failed, aborting the auth flow.'.format(challenge['challengeMetadata'])
                return
    # The user has not answered the challenge yet.
    # This response tells Cognito to send a custom challenge to the user.
    event['response']['challengeName'] = 'CUSTOM_CHALLENGE'

# This sets up the parameters for the custom challenge.
# The 'BasicAuth' custom challenge type is used for normal users, and requires the user's password.
# The 'ForceChangePassword' custom challenge is used when Cogntio requires a password change before authentication can be completed.
def create_auth_challenge(event):
    if event['request'].get('userAttributes', {}).get('cognito:user_status') == 'FORCE_CHANGE_PASSWORD':
        event['response']['publicChallengeParameters'] = {'type': 'ForceChangePassword'}
        event['response']['privateChallengeParameters'] = {'type': 'ForceChangePassword'}
        event['response']['challengeMetadata'] = 'ForceChangePassword'
    else:
        event['response']['publicChallengeParameters'] = {'type': 'BasicAuth'}
        event['response']['privateChallengeParameters'] = {'type': 'BasicAuth'}
        event['response']['challengeMetadata'] = 'BasicAuth'

# Verifies the user's answer for the 'BasicAuth' and 'ForceChangePassword' challenge types by forwarding the password(s) to the admin API.
# If that was successful, it ensures that the user has an identity in the Cognito identity pool and
# creates or updates the account's username mapping.
def verify_auth_challenge_response(event):
    if 'privateChallengeParameters' not in event['request'] or 'type' not in event['request']['privateChallengeParameters']:
        print 'The request is missing privateChallengeParameters.type'
        event['response']['answerCorrect'] = False
        return

    challenge_type = event['request']['privateChallengeParameters']['type']
    password = None
    new_password = None
    if challenge_type == 'BasicAuth':
        password = event['request']['challengeAnswer']
    elif challenge_type == 'ForceChangePassword':
        try:
            answer = json.loads(event['request']['challengeAnswer'])
        except ValueError as e:
            print 'Unable to parse the answer for ForceChangePassword as json'
            event['response']['answerCorrect'] = False
            return

        password = answer.get('password')
        new_password = answer.get('newPassword')
        if password == None or new_password == None:
            print 'The answer for the ForceChangePassword challenge is missing the password or newPassword.'
            event['response']['answerCorrect'] = False
            return
    else:
        print 'Unsupported challenge type: {}'.format(challenge_type)
        event['response']['answerCorrect'] = False
        return

    # Use the provided username and password to attempt authentication using the admin API.
    try:
        idpResponse = account_utils.get_user_pool_client().admin_initiate_auth(
            UserPoolId = event['userPoolId'],
            ClientId = event['callerContext']['clientId'],
            AuthFlow = 'ADMIN_NO_SRP_AUTH',
            AuthParameters = {
                'USERNAME': event['userName'],
                'PASSWORD': password
            }
        )
    except:
        traceback.print_exc()
        raise errors.ClientError("Authentication failed")

    if 'AuthenticationResult' not in idpResponse:
        if 'ChallengeName' in idpResponse:
            print 'The response from AdminInitiateAuth contained a {} challenge.'.format(idpResponse.get('ChallengeName'))

        if idpResponse.get('ChallengeName') == 'NEW_PASSWORD_REQUIRED':
            idpResponse = account_utils.get_user_pool_client().admin_respond_to_auth_challenge(
                UserPoolId=event['userPoolId'],
                ClientId=event['callerContext']['clientId'],
                ChallengeName='NEW_PASSWORD_REQUIRED',
                ChallengeResponses={
                    'NEW_PASSWORD': new_password,
                    'USERNAME': event['userName']
                },
                Session=idpResponse['Session']
            )

            if 'AuthenticationResult' not in idpResponse:
                if 'ChallengeName' in idpResponse:
                    print 'The response from AdminInitiateAuth contained a {} challenge.'.format(idpResponse.get('ChallengeName'))
                print 'Authentication failed: the response from AdminInitiateAuth did not contain AuthenticationResult'
                event['response']['answerCorrect'] = False
                return
        else:
            print 'Authentication failed: the response from AdminInitiateAuth did not contain AuthenticationResult'
            event['response']['answerCorrect'] = False
            return

    if 'IdToken' not in idpResponse['AuthenticationResult']:
        print 'The response from AdminInitiateAuth did not contain an IdToken'
        event['response']['answerCorrect'] = False
        return

    # Use the token to get the identity for the user.
    provider_id = 'cognito-idp.' + event['region'] + '.amazonaws.com/' + event['userPoolId']
    idResponse = account_utils.get_identity_pool_client().get_id(
        IdentityPoolId = account_utils.get_identity_pool_id(),
        Logins = {
            provider_id: idpResponse['AuthenticationResult']['IdToken']
        }
    )

    if 'IdentityId' not in idResponse:
        print 'The response from GetId did not contain an IdentityId'
        event['response']['answerCorrect'] = False
        return

    # Update the identity to username mapping.
    account = account_utils.get_account_for_identity(idResponse['IdentityId'])
    if account:
        if account.get('AccountBlacklisted'):
            raise errors.ClientError("Authentication failed: the account is blacklisted")

        account_utils.update_account({
             'AccountId': account['AccountId'],
             'CognitoIdentityId': idResponse['IdentityId'],
             'CognitoUsername': event['userName']
        })
    else:
        account_utils.create_account({
             'AccountId': str(uuid.uuid4()),
             'CognitoIdentityId': idResponse['IdentityId'],
             'CognitoUsername': event['userName']
        })

    event['response']['answerCorrect'] = True