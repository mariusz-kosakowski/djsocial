# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django import forms
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _

from tweepy import OAuthHandler
import tweepy
from models import ScheduleOrder, Twitter


class OrderTypeForm(forms.Form):
    """ OrderTypeForm
    TODO: Add validation to allow every user for X amount of active schdule jobs
    """
    order_types = (
        ('follow_form', _('Auto follow back')),
        ('unfollow_form', _('Auto unfollow back')),
        ('retweet_form', _('Auto retweet')),
        ('favorite_form', _('Auto favirote')),
    )
    order_type = forms.ChoiceField(choices=order_types, widget=forms.Select(attrs={'class': 'form-control'}))

    def __init__(self, *args, **kwargs):
        self.user = kwargs.get('user') or None
        kwargs.pop('user')
        super(OrderTypeForm, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = self.cleaned_data
        scheduled_orders_count = ScheduleOrder.objects.filter(user=get_object_or_404(Twitter, user=self.user),
                                                              run_once=False).count()
        MAX_SCHEDULED_ORDERS_PER_USER = getattr(settings, 'MAX_SCHEDULED_ORDERS_PER_USER', 5)
        if scheduled_orders_count >= MAX_SCHEDULED_ORDERS_PER_USER:
            raise forms.ValidationError(_('No more than "{}" orders per user'.format(MAX_SCHEDULED_ORDERS_PER_USER)))
        return cleaned_data


class RelationshipForm(forms.ModelForm):
    """ RelationshipForm
    """
    operation_options = (
        ('follow', _('Follow')),
        ('unfollow', _('Unfollow')),
    )
    operation = forms.ChoiceField(choices=operation_options, widget=forms.HiddenInput)
    exclude = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': '3'}),
                              help_text=_('Use comma separated username that you want to exclude'), required=False)

    class Meta:
        model = ScheduleOrder
        fields = ('operation', 'exclude')

    def __init__(self, *args, **kwargs):
        self.user = kwargs.get('user') or None
        kwargs.pop('user')
        super(RelationshipForm, self).__init__(*args, **kwargs)

    def save(self, commit=True):
        cleaned_data = self.cleaned_data
        obj = super(RelationshipForm, self).save(commit=commit)

        obj.label = '{0} back: runs hourly'.format(cleaned_data.get('operation'))
        obj.run_once = False
        obj.func = cleaned_data.get('operation')
        obj.kwargs = {'exclude': cleaned_data.get('exclude') or '',
                      'func': cleaned_data.get('operation'), }
        return obj

    def clean(self):
        cleaned_data = self.cleaned_data
        try:
            label = '{0} back: runs hourly'.format(cleaned_data.get('operation'))
            obj = ScheduleOrder.objects.get(label=label, user=get_object_or_404(Twitter, user=self.user),
                                            run_once=False)
            raise forms.ValidationError(_('This is a duplicate setup, you already have "{}"'.format(obj.label)))
        except ScheduleOrder.DoesNotExist:
            pass
        return cleaned_data


class AutoTweetForm(forms.Form):
    """
    """
    auto_tweet_options = (
        ('USER', 'By specific user(s)'),
        ('SEARCH', 'By Search criteria'),
    )
    auto_tweet_operation = forms.ChoiceField(choices=auto_tweet_options,
                                             widget=forms.Select(attrs={'class': 'form-control'}))

    def __init__(self, *args, **kwargs):
        self.user = kwargs.get('user') or None
        kwargs.pop('user')
        super(AutoTweetForm, self).__init__(*args, **kwargs)


class AutoTweetSearchForm(forms.ModelForm):
    """ AutoTweetForm
    """
    operation_options = (
        ('favorite', _('favorite')),
        ('retweet', _('retweet')),
    )
    search_style_options = (
        (0, 'Search once a day, re-tweet result every hour'),
        (0, 'Search every hour, re-tweet result'),
    )
    operation = forms.ChoiceField(choices=operation_options, widget=forms.HiddenInput)

    search_by_hash_tag = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}), help_text=_(
        'Hash Tag will be used to search for tweets desired for retweeting'))

    search_style = forms.ChoiceField(choices=search_style_options, widget=forms.Select(attrs={'class': 'form-control'}))

    minimum_favorite = forms.DecimalField(initial=0, widget=forms.TextInput(
        attrs={'class': 'form-control', 'data-group-class': 'col-xs-3'}), )

    minimum_retweet = forms.DecimalField(initial=0, widget=forms.TextInput(
        attrs={'class': 'form-control', 'data-group-class': 'col-xs-3'}), )

    class Meta:
        model = ScheduleOrder
        fields = ('search_by_hash_tag', 'search_style', 'minimum_favorite',
                  'minimum_retweet', 'operation')

    def __init__(self, *args, **kwargs):
        self.user = kwargs.get('user') or None
        kwargs.pop('user')
        super(AutoTweetSearchForm, self).__init__(*args, **kwargs)

    def clean_search_by_hash_tag(self):
        data = self.cleaned_data['search_by_hash_tag']
        # add validation for search field / must be twitter slug compatible
        return [data, ]

    def clean_operation(self):
        # add validation for search field / must be twitter slug compatible
        data = '{}_search'.format(self.cleaned_data['operation'])
        return data

    def get_order_values(self):
        cleaned_data = self.cleaned_data
        func = cleaned_data.get('operation')
        args = cleaned_data.get('search_by_hash_tag')
        kwargs = {'search_style': cleaned_data.get('search_style') or None,
                  'func': cleaned_data.get('operation').replace('_search', ''),
                  'minimum_favorite': cleaned_data.get('minimum_favorite') or None,
                  'minimum_retweet': cleaned_data.get('minimum_retweet') or None}
        search_hash_tag = cleaned_data.get('search_by_hash_tag')
        if isinstance(search_hash_tag, list):
            search_hash_tag = ''.join(search_hash_tag)
        label = 'search for {0} and {1} - hourly'.format(search_hash_tag,
                                                         cleaned_data.get('operation').replace('_search', ''))
        run_once = False
        return func, args, kwargs, label, run_once

    def save(self, commit=True):
        obj = super(AutoTweetSearchForm, self).save(commit=commit)
        obj.func, obj.args, obj.kwargs, obj.label, obj.run_once = self.get_order_values()
        return obj

    def clean(self):
        cleaned_data = self.cleaned_data
        try:
            func, args, kwargs, label, run_once = self.get_order_values()

            obj = ScheduleOrder.objects.get(func=func,
                                            args=args,
                                            kwargs=kwargs,
                                            user=get_object_or_404(Twitter, user=self.user),
                                            run_once=False)
            raise forms.ValidationError(_('This is a duplicate setup, you already have "{}"'.format(obj.label)))
        except ScheduleOrder.DoesNotExist:
            pass
        return cleaned_data


class AutoTweetUserForm(forms.ModelForm):
    """ AutoTweetForm
    """
    operation_options = (
        ('favorite', _('favorite')),
        ('retweet', _('retweet')),
    )
    operation = forms.ChoiceField(choices=operation_options, widget=forms.HiddenInput)

    twitter_user = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}),
                                   help_text=_('Comma separated value, specify users you want watch (4 users maximum)'))

    minimum_favorite = forms.DecimalField(initial=0, widget=forms.TextInput(
        attrs={'class': 'form-control', 'data-group-class': 'col-xs-3'}), )

    minimum_retweet = forms.DecimalField(initial=0, widget=forms.TextInput(
        attrs={'class': 'form-control', 'data-group-class': 'col-xs-3'}), )

    class Meta:
        model = ScheduleOrder
        fields = ('twitter_user', 'minimum_favorite', 'minimum_retweet', 'operation')

    def __init__(self, *args, **kwargs):
        self.user = kwargs.get('user') or None
        kwargs.pop('user')
        super(AutoTweetUserForm, self).__init__(*args, **kwargs)

    def clean_twitter_user(self):
        # will return list so it can be passed into kwargs dictionary
        data = self.cleaned_data['twitter_user']
        users = data.split(',')
        users = [x.strip() for x in users if x.strip() not in ('', u'')]
        if len(users) > 4:
            raise forms.ValidationError(_('Only 4 users maximum'))

        if sorted(users) != sorted(list(set(users))):
            raise forms.ValidationError(_('You must provide unique users'))
        return users

    def clean_operation(self):
        # add validation for search field / must be twitter slug compatible
        data = '{}_watch'.format(self.cleaned_data['operation'])
        return data

    def get_order_values(self):
        cleaned_data = self.cleaned_data
        func = cleaned_data.get('operation')
        args = cleaned_data.get('twitter_user') or None
        kwargs = {'minimum_favorite': cleaned_data.get('minimum_favorite') or None,
                  'func': cleaned_data.get('operation').replace('_watch', ''),
                  'minimum_retweet': cleaned_data.get('minimum_retweet') or None}

        label = 'watch {0} and {1} - hourly'.format(
            ','.join(['@{}'.format(i) for i in cleaned_data.get('twitter_user')]),
            cleaned_data.get('operation').replace('_watch', ''))
        run_once = False
        return func, args, kwargs, label, run_once

    def save(self, commit=True):
        obj = super(AutoTweetUserForm, self).save(commit=commit)
        obj.func, obj.args, obj.kwargs, obj.label, obj.run_once = self.get_order_values()
        return obj

    def clean(self):
        cleaned_data = self.cleaned_data
        func, args, kwargs, label, run_once = self.get_order_values()
        try:
            # validate that each user used in the comma separated values is unique for the operation
            # user cannot add the same user for auto-retweet twice in different sets. This will ensure that
            for arg in args:
                obj = ScheduleOrder.objects.filter(func=func,
                                                   args__contains=arg,
                                                   user=get_object_or_404(Twitter, user=self.user),
                                                   run_once=False)
                if len(obj) > 0: raise forms.ValidationError(
                    _('The user {} already used in similar operation'.format(arg)))
        except forms.ValidationError:
            raise

        try:
            # this will ensure that the same exact scheduled job is not done twice
            obj = ScheduleOrder.objects.get(func=func,
                                            args__contains=args,
                                            kwargs=kwargs,
                                            user=get_object_or_404(Twitter, user=self.user),
                                            run_once=False)

            raise forms.ValidationError(_('This is a duplicate setup, you already have "{}"'.format(obj.label)))
        except ScheduleOrder.DoesNotExist:
            pass

        try:
            users = args
            for user in users:
                auth = OAuthHandler(getattr(settings, 'TWITTER_CONSUMER_KEY'),
                                    getattr(settings, 'TWITTER_CONSUMER_SECRET'))
                account = Twitter.objects.get(user_id=self.user.id)
                auth.set_access_token(account.access_token, account.secret_key)
                api = tweepy.API(auth)
                try:
                    api.get_user(user)
                except:
                    raise forms.ValidationError(_('User {} does not exist on twitter'.format(user)))
        except:
            raise

        return cleaned_data