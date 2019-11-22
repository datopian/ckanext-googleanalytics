from __future__ import absolute_import
from future import standard_library

standard_library.install_aliases()
from builtins import str
from builtins import range
import ast
import logging
import urllib.request, urllib.parse, urllib.error
import ckanext.googleanalytics.commands as commands
import paste.deploy.converters as converters
import ckan.lib.helpers as h
import ckan.plugins as p
import ckan.plugins.toolkit as tk
import urllib.request, urllib.error, urllib.parse
from ckan.exceptions import CkanVersionException
import threading

log = logging.getLogger(__name__)

try:
    tk.requires_ckan_version("2.9")
except CkanVersionException:
    from ckanext.googleanalytics.plugin.paster_plugin import GAMixinPlugin
else:
    from ckanext.googleanalytics.plugin.flask_plugin import GAMixinPlugin


class GoogleAnalyticsException(Exception):
    pass


class AnalyticsPostThread(threading.Thread):
    """Threaded Url POST"""

    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.queue = queue

    def run(self):
        while True:
            # grabs host from queue
            data_dict = self.queue.get()

            data = urllib.parse.urlencode(data_dict)
            log.debug("Sending API event to Google Analytics: " + data)
            # send analytics
            urllib.request.urlopen(
                "http://www.google-analytics.com/collect",
                data,
                # timeout in seconds
                # https://docs.python.org/2/library/urllib2.html#urllib2.urlopen
                10,
            )

            # signals to queue job is done
            self.queue.task_done()


class GoogleAnalyticsPlugin(GAMixinPlugin, p.SingletonPlugin):
    p.implements(p.IConfigurable, inherit=True)
    p.implements(p.IConfigurer, inherit=True)
    p.implements(p.ITemplateHelpers)

    def configure(self, config):
        """Load config settings for this extension from config file.

        See IConfigurable.

        """
        if "googleanalytics.id" not in config:
            msg = "Missing googleanalytics.id in config"
            raise GoogleAnalyticsException(msg)
        self.googleanalytics_id = config["googleanalytics.id"]
        self.googleanalytics_domain = config.get(
            "googleanalytics.domain", "auto"
        )
        self.googleanalytics_fields = ast.literal_eval(
            config.get("googleanalytics.fields", "{}")
        )

        googleanalytics_linked_domains = config.get(
            "googleanalytics.linked_domains", ""
        )
        self.googleanalytics_linked_domains = [
            x.strip() for x in googleanalytics_linked_domains.split(",") if x
        ]

        if self.googleanalytics_linked_domains:
            self.googleanalytics_fields["allowLinker"] = "true"

        self.googleanalytics_javascript_url = h.url_for_static(
            "/scripts/ckanext-googleanalytics.js"
        )

        # If resource_prefix is not in config file then write the default value
        # to the config dict, otherwise templates seem to get 'true' when they
        # try to read resource_prefix from config.
        if "googleanalytics_resource_prefix" not in config:
            config[
                "googleanalytics_resource_prefix"
            ] = commands.DEFAULT_RESOURCE_URL_TAG
        self.googleanalytics_resource_prefix = config[
            "googleanalytics_resource_prefix"
        ]

        self.show_downloads = converters.asbool(
            config.get("googleanalytics.show_downloads", True)
        )
        self.track_events = converters.asbool(
            config.get("googleanalytics.track_events", False)
        )
        self.enable_user_id = converters.asbool(
            config.get("googleanalytics.enable_user_id", False)
        )

        if not converters.asbool(config.get("ckan.legacy_templates", "false")):
            p.toolkit.add_resource(
                "../fanstatic_library", "ckanext-googleanalytics"
            )

            # spawn a pool of 5 threads, and pass them queue instance
        for i in range(5):
            t = AnalyticsPostThread(self.analytics_queue)
            t.setDaemon(True)
            t.start()

    def update_config(self, config):
        """Change the CKAN (Pylons) environment configuration.

        See IConfigurer.

        """
        if converters.asbool(config.get("ckan.legacy_templates", "false")):
            p.toolkit.add_template_directory(config, "../legacy_templates")
            p.toolkit.add_public_directory(config, "../legacy_public")
        else:
            p.toolkit.add_template_directory(config, "../templates")

    def get_helpers(self):
        """Return the CKAN 2.0 template helper functions this plugin provides.

        See ITemplateHelpers.

        """
        return {"googleanalytics_header": self.googleanalytics_header}

    def googleanalytics_header(self):
        """Render the googleanalytics_header snippet for CKAN 2.0 templates.

        This is a template helper function that renders the
        googleanalytics_header jinja snippet. To be called from the jinja
        templates in this extension, see ITemplateHelpers.

        """

        if self.enable_user_id and tk.c.user:
            self.googleanalytics_fields["userId"] = str(tk.c.userobj.id)

        data = {
            "googleanalytics_id": self.googleanalytics_id,
            "googleanalytics_domain": self.googleanalytics_domain,
            "googleanalytics_fields": str(self.googleanalytics_fields),
            "googleanalytics_linked_domains": self.googleanalytics_linked_domains,
        }
        return p.toolkit.render_snippet(
            "googleanalytics/snippets/googleanalytics_header.html", data
        )
