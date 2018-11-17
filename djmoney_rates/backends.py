from __future__ import unicode_literals

import logging
import json

from django.core.exceptions import ImproperlyConfigured
from django.utils import six

try:
    from urllib2 import urlopen
except ImportError:
    from urllib.request import urlopen

from .exceptions import RateBackendError
from .models import RateSource, Rate
from .settings import money_rates_settings
import datetime


logger = logging.getLogger(__name__)


class BaseRateBackend(object):
    source_name = None
    base_currency = None

    def get_source_name(self):
        """
        Return the name that identifies the ratings source
        """
        if not self.source_name:
            raise RateBackendError("'source_name' can't be empty or "
                                   "you should override 'get_source_name'")

        return self.source_name

    def get_base_currency(self):
        """
        Return the base currency to which the rates are referred
        """
        if not self.base_currency:
            raise RateBackendError("'base_currency' can't be empty or "
                                   "you should override 'get_base_currency'")

        return self.base_currency

    def get_rates(self):
        """
        Return a dictionary that maps currency code with its rate value
        """
        raise NotImplementedError

    def update_rates(self, date):
        """
        Creates or updates rates for a source
        """
        source, created = RateSource.objects.get_or_create(name=self.get_source_name())
        source.base_currency = self.get_base_currency()
        source.save()

        for currency, value in six.iteritems(self.get_rates(date=date)):
            try:
                rate = Rate.objects.get(source=source, currency=currency, date = date)
            except Rate.DoesNotExist:
                rate = Rate(source=source, currency=currency, date = date)

            rate.value = value
            rate.save()


class OpenExchangeBackend(BaseRateBackend):
    source_name = "openexchange.org"

    def __init__(self):
        if not money_rates_settings.OPENEXCHANGE_URL_LATEST:
            raise ImproperlyConfigured(
                "OPENEXCHANGE_URL_LATEST setting should not be empty when using OpenExchangeBackend")
        if not money_rates_settings.OPENEXCHANGE_URL_HISTORICAL:
            raise ImproperlyConfigured(
                "OPENEXCHANGE_URL_HISTORICAL setting should not be empty when using OpenExchangeBackend")

        if not money_rates_settings.OPENEXCHANGE_APP_ID:
            raise ImproperlyConfigured(
                "OPENEXCHANGE_APP_ID setting should not be empty when using OpenExchangeBackend")

    def _get_url(self, date):
        if (date == datetime.date.today()):
            base_url = "%s?app_id=%s" % (money_rates_settings.OPENEXCHANGE_URL_LATEST,
                                     money_rates_settings.OPENEXCHANGE_APP_ID)
        else:
            historical_url = money_rates_settings.OPENEXCHANGE_URL_HISTORICAL % str(date)
            base_url = "%s?app_id=%s" % (historical_url, money_rates_settings.OPENEXCHANGE_APP_ID)

        # Change the base currency whether it is specified in settings
        base_url += "&base=%s" % self.get_base_currency()

        base_url += "&show_alternative=true"

        return base_url

    def get_rates(self, date):

        url = self._get_url(date)

        try:
            logger.debug("Connecting to url %s" % url)
            data = urlopen(url).read().decode("utf-8")
            return json.loads(data)['rates']

        except Exception as e:
            logger.exception("Error retrieving data from %s", url)
            raise RateBackendError("Error retrieving rates: %s" % e)

    def get_base_currency(self):
        return money_rates_settings.OPENEXCHANGE_BASE_CURRENCY
