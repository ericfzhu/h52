import type { Metadata } from 'next';
import { Cabin } from 'next/font/google';
import './globals.css';

const cabin = Cabin({ subsets: ['latin'] });

export const dynamic = 'force-static';
export const metadata: Metadata = {
	title: 'Hermes 52',
	description: 'Leather goods push notification service',
};

export default function RootLayout({
	children,
}: Readonly<{
	children: React.ReactNode;
}>) {
	return (
		<html lang="en">
			<link rel="icon" href="/icon.png" />
			<body className={cabin.className}>{children}</body>
		</html>
	);
}
