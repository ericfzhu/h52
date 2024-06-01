import Image from "next/image";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24 bg-[#F6F1EB]">
      {/* <h1 className="text-black">H52</h1> */}
      <h1>
        <Image
          src="/logo.png"
          alt="H52"
          width="500"
          height="500"
          className="w-36"
        />
      </h1>
    </main>
  );
}
