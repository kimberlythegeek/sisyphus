# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from django.contrib.auth.models import User
from django_auth_ldap.backend import LDAPBackend


class MozillaLDAPBackend(LDAPBackend):
    """Overriding this class so that I can transform emails to usernames.

    At Mozilla we use email addresses as the username but in django I want,
    for example:
        INPUT:
            username -> pbengtsson@mozilla.com
        OUTPUT:
            username -> pbengtsson
            email -> pbengtsson@mozilla.com

    I can map (in settings.AUTH_LDAP_USER_ATTR_MAP):
        'username' -> 'uid'
        and
        'email -> 'mail

    But that means that the second time a user logs in, it's not going to
    find a username that is 'pbengtsson@mozilla.com' so it'll go ahead and
    create it again and you'll end up with duplicates once the attribute
    conversion is done.

    The other thing that this backend accomplishes is to change username
    entirely. Suppose, for example, that your mozilla LDAP email is
    'pbengtsson@mozilla.com' but you prefer your own custom alias of
    'peterbe'. What it does then, is looking at existing users that match
    the *email address* and returns the username for that one.
    """

    def get_or_create_user(self, username, ldap_user):
        """
        This must return a (User, created) 2-tuple for the given LDAP user.
        username is the Django-friendly username of the user. ldap_user.dn is
        the user's DN and ldap_user.attrs contains all of their LDAP attributes.
        """
        # users on this site can't change their email but they can change their
        # username
        if ldap_user.attrs.get('mail'):
            for user in (User.objects
              .filter(email__iexact=ldap_user.attrs.get('mail')[0])):
                return (user, False)

        # use the default from django-auth-ldap
        return User.objects.get_or_create(
           username__iexact=username,
           defaults={'username': username.lower()}
        )


    def ldap_to_django_username(self, username):
        """Allow users to use a different username"""
        try:
            return User.objects.get(email=username).username
        except User.DoesNotExist:
            return username.split('@')[0]

    def supports_inactive_user(self):
        return False


class EmailOrUsernameModelBackend(object):
    """Simple auth back end to check against local db by email or username.
    """

    supports_object_permissions = False
    supports_anonymous_user = False
    supports_inactive_user = False

    def authenticate(self, username=None, password=None):
        if '@' in username:
            kwargs = {'email__iexact': username}
        else:
            kwargs = {'username': username}
        try:
            user = User.objects.get(**kwargs)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            pass
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:  # pragma: no cover
            return None
