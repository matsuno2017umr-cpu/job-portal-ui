const CookiePolicy = () => {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
      <h1 className="text-4xl font-black bg-gradient-to-r from-primary-500 to-purple-600 bg-clip-text text-transparent mb-8">
        Cookie Policy
      </h1>

      <div className="space-y-8 text-gray-700 dark:text-gray-300 leading-relaxed">
        <section>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
            What Are Cookies
          </h2>
          <p>
            Cookies are small text files stored on your device when you visit
            JobPortal. They help us remember your preferences and improve
            your experience across the site.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
            How We Use Cookies
          </h2>
          <p>
            We use cookies to keep you signed in, remember your theme
            preference, and understand how visitors use JobPortal so we can
            make it better.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
            Managing Cookies
          </h2>
          <p>
            You can control or delete cookies through your browser settings
            at any time. Disabling cookies may affect some features of
            JobPortal, such as staying signed in.
          </p>
        </section>
      </div>
    </div>
  );
};

export default CookiePolicy;
