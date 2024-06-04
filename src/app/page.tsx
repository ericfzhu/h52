'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useState, useEffect } from 'react';
import Papa from 'papaparse';
import { cn } from '@/lib/utils';

interface Item {
	uuid: string;
	item_id: string;
	timestamp: number;
	price: number;
	url: string;
	color: string;
	title: string;
	is_new: number;
}

function getWeekNumber(date: Date) {
	const firstDayOfYear = new Date(date.getFullYear(), 0, 1);
	const pastDaysOfYear = (date.getTime() - firstDayOfYear.getTime()) / 86400000;
	return Math.ceil((pastDaysOfYear + firstDayOfYear.getDay() + 1) / 7);
}

const formatDate = (key: string, groupBy: 'day' | 'week'): string => {
	if (groupBy === 'day') {
		const [year, month, day] = key.split('-');
		return new Date(Number(year), Number(month) - 1, Number(day)).toLocaleString('en-US', {
			month: 'short',
			day: '2-digit',
			year: 'numeric',
		});
	} else {
		const [year, week] = key.split('-W');
		return `Week ${week}, ${year}`;
	}
};

export default function Home() {
	const [items, setItems] = useState<Item[]>([]);
	const [groupBy, setGroupBy] = useState<'day' | 'week'>('day');
	// console.log(items);

	useEffect(() => {
		const fetchData = async () => {
			const response = await fetch('/output_updated.csv');
			const csvData = await response.text();

			const { data } = Papa.parse<Item>(csvData, {
				header: true,
				dynamicTyping: true,
			});

			setItems(data);
		};

		fetchData();
	}, []);

	const filteredItems = items.filter((item) => item.is_new === 1);

	const groupedItems = filteredItems.reduce(
		(acc, item) => {
			const date = new Date(item.timestamp * 1000);
			const key = groupBy === 'day' ? date.toISOString().slice(0, 10) : `${date.getFullYear()}-W${getWeekNumber(date)}`;

			if (!acc[key]) {
				acc[key] = [];
			}

			if (!acc[key]) {
				acc[key] = [];
			}

			if (!acc[key].some((i) => i.item_id === item.item_id)) {
				acc[key].push(item);
			}

			return acc;
		},
		{} as Record<string, Item[]>,
	);

	console.log(items);
	return (
		<main className="flex min-h-screen w-full flex-col items-center gap-20 bg-[#F6F1EB] px-24">
			{/* <h1 className="text-black">H52</h1> */}
			<h1 className="pt-12">
				<Image src="/logo.png" alt="H52" width="500" height="222" className="h-auto w-36" />
			</h1>
			<div className="w-full max-w-xl text-[#474747]">
				<div className="flex gap-8">
					<button className={cn('uppercase', groupBy === 'day' ? 'font-bold' : '')} onClick={() => setGroupBy('day')}>
						Day
					</button>
					<button className={cn('uppercase', groupBy === 'week' ? 'font-bold' : '')} onClick={() => setGroupBy('week')}>
						Week
					</button>
				</div>
				{Object.entries(groupedItems)
					.map(([date, items]) => ({
						date,
						items: items.sort((a, b) => a.title.localeCompare(b.title) || a.color.localeCompare(b.color)),
					}))
					.reverse()
					.map(({ date, items }) => (
						<div key={date} className="flex flex-col gap-2 py-10 font-light">
							<h2 className="text-center">{formatDate(date, groupBy)}</h2>
							<div className="flex flex-col gap-2">
								{items.map((item) => (
									<Link
										key={item.uuid}
										className="flex duration-300 hover:text-[#EC6C1F]"
										href={`https://www.hermes.com${item.url}`}
										target="_blank">
										<h3 className="w-[70%]">{item.title}</h3>
										<p className="w-[20%]">{item.color}</p>
										<p className="w-[10%]">{item.price}</p>
									</Link>
								))}
							</div>
						</div>
					))}
			</div>
		</main>
	);
}
