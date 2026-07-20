const TermsOfService = () => {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
      <h1 className="text-4xl font-black bg-gradient-to-r from-primary-500 to-purple-600 bg-clip-text text-transparent mb-8">
        Terms of Service
      </h1>

      <div className="space-y-8 text-gray-700 dark:text-gray-300 leading-relaxed">
        <section>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
            Acceptance of Terms
          </h2>
          <p>
            By accessing or using JobPortal, you agree to be bound by these
            Terms of Service. If you do not agree to these terms, please do
            not use our platform.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
            Use of the Platform
          </h2>
          <p>
            JobPortal connects job seekers with employers. You agree to
            provide accurate information and to use the platform only for
            lawful purposes related to seeking or offering employment.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
            Account Responsibility
          </h2>
          <p>
            You are responsible for maintaining the confidentiality of your
            account credentials and for all activity that occurs under your
            account.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
            Changes to These Terms
          </h2>
          <p>
            We may update these Terms of Service from time to time. Continued
            use of JobPortal after changes take effect constitutes acceptance
            of the revised terms.
          </p>
        </section>
      </div>
    </div>
  );
};

export default TermsOfService;
