
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.test import TestCase

from django.http import HttpRequest
from django.contrib.auth import authenticate

from forms_builder.forms.models import Form, STATUS_DRAFT, STATUS_PUBLISHED
from forms_builder.forms.fields import NAMES
from forms_builder.forms.settings import USE_SITES
from forms_builder.forms.signals import form_invalid, form_valid
from forms_builder.forms.views import form_detail

current_site = None
if USE_SITES:
    current_site = Site.objects.get_current()


class Tests(TestCase):

    def test_form_fields(self):
        """
        Simple 200 status check against rendering and posting to forms with
        both optional and required fields.
        """
        username = "dtest"
        password = "test"
        User.objects.create_superuser(username, "", password)
        for required in (True, False):
            form = Form.objects.create(title="Test", slug="test", status=STATUS_PUBLISHED)
            if USE_SITES:
                form.sites.add(current_site)
                form.save()
            for (field, _) in NAMES:
                form.fields.create(label=field, field_type=field,
                                   required=required, visible=True)
            response = self.client.get(form.get_absolute_url())
            self.assertEqual(response.status_code, 200)
            fields = form.fields.visible()
            data = dict([("field_%s" % f.id, "test") for f in fields])
            response = self.client.post(form.get_absolute_url(), data=data)
            # "View on site" submit button redirects back to admin/forms/form page
            self.assertEqual(response.status_code, 302)
            # So submit the form directly to get the 200 response
            req = HttpRequest()
            req.method = "POST"
            req.user = authenticate(username=username, password=password)
            response = form_detail(req, "test")
            self.assertEqual(response.status_code, 200)
            #
            form.delete()

    def test_draft_form(self):
        """
        Test that a form with draft status is only visible to staff.
        """
        settings.DEBUG = True # Don't depend on having a 404 template.
        username = "test"
        password = "test"
        User.objects.create_superuser(username, "", password)
        self.client.logout()
        draft = Form.objects.create(title="Draft", status=STATUS_DRAFT)
        if USE_SITES:
            draft.sites.add(current_site)
            draft.save()
        response = self.client.get(draft.get_absolute_url())
        self.assertEqual(response.status_code, 404)
        self.client.login(username=username, password=password)
        response = self.client.get(draft.get_absolute_url())
        self.assertEqual(response.status_code, 200)

    def test_form_signals(self):
        """
        Test that each of the signals are sent.
        """
        events = ["valid", "invalid"]
        invalid = lambda **kwargs: events.remove("invalid")
        form_invalid.connect(invalid)
        valid = lambda **kwargs: events.remove("valid")
        form_valid.connect(valid)
        form = Form.objects.create(title="Signals", slug='signals', status=STATUS_PUBLISHED)
        if USE_SITES:
            form.sites.add(current_site)
            form.save()
        form.fields.create(label="field", field_type=NAMES[0][0],
                           required=True, visible=True)
        #
        # Create an HttpRequest object that can be passed directly to a view function,
        # specifically to form_detail() which accepts form POST data
        username = "test"
        password = "test"
        User.objects.create_superuser(username, "", password)
        req = HttpRequest()
        req.method = "POST"
        req.user = authenticate(username=username, password=password)
        #
        form_detail(req, "signals")
        data = {"field_%s" % form.fields.visible()[0].id: "test"}
        req.POST.update(data)
        form_detail(req, "signals")
        self.assertEqual(len(events), 0)
