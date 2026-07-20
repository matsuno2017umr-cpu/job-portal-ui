const PrivacyPolicy = () => {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
      <h1 className="text-4xl font-black bg-gradient-to-r from-primary-500 to-purple-600 bg-clip-text text-transparent mb-8">
        Privacy Policy
      </h1>

      <div className="space-y-8 text-gray-700 dark:text-gray-300 leading-relaxed">
        <section>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
            Information We Collect
          </h2>
          <p>
            When you use JobPortal, we collect information you provide
            directly, such as your name, email address, resume, and job
            application details, as well as usage data that helps us
            operate the platform.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
            How We Use Your Information
          </h2>
          <p>
            We use your information to match you with relevant job
            opportunities, connect employers with candidates, communicate
            with you about your account, and improve JobPortal's features.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
            Sharing Your Information
          </h2>
          <p>
            We share your profile and application details only with
            employers you apply to, and do not sell your personal
            information to third parties.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
            Your Choices
          </h2>
          <p>
            You can review, update, or delete your account information at
            any time from your profile settings. Contact us if you have
            questions about how your data is handled.
          </p>
        </section>
      </div>
    </div>
  );
};

export default PrivacyPolicy;
