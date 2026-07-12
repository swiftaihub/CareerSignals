import { z } from "zod";

export const PASSWORD_MIN_LENGTH = 10;

export const RESET_REQUEST_SUCCESS_MESSAGE =
  "If an account exists for this email, CareerSignals will send password reset instructions shortly.";

export const PASSWORD_RESET_SUCCESS_MESSAGE =
  "Your CareerSignals password has been updated. Please sign in with your new password.";

export const PASSWORD_CHANGE_SUCCESS_MESSAGE =
  "Your CareerSignals password has been changed. Please sign in with your new password.";

export const DEMO_PASSWORD_CHANGE_MESSAGE =
  "Password changes are unavailable for the demo account.";

export const passwordSchema = z.string().min(
  PASSWORD_MIN_LENGTH,
  `Password must be at least ${PASSWORD_MIN_LENGTH} characters.`
);

export const resetRequestSchema = z.object({
  email: z.email("Enter a valid email address.")
});

const passwordConfirmationShape = {
  newPassword: passwordSchema,
  confirmPassword: z.string()
};

function passwordsMatch({
  newPassword,
  confirmPassword
}: {
  newPassword: string;
  confirmPassword: string;
}) {
  return newPassword === confirmPassword;
}

const passwordMismatchOptions = {
  message: "Passwords do not match.",
  path: ["confirmPassword"]
};

export const resetPasswordSchema = z
  .object(passwordConfirmationShape)
  .refine(passwordsMatch, passwordMismatchOptions);

export const changePasswordSchema = z
  .object({
    currentPassword: z.string().min(1, "Enter your current password."),
    ...passwordConfirmationShape
  })
  .refine(passwordsMatch, passwordMismatchOptions);
