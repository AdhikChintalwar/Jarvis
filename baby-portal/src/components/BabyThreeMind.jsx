import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Stars, Line, Text } from "@react-three/drei";
import { useRef, useMemo } from "react";
import * as THREE from "three";

const AGENTS = [
    { id: "desktop", color: "#6be5ff", radius: 3.4, speed: 0.21 },
    { id: "browser", color: "#00ff99", radius: 3.75, speed: 0.18 },
    { id: "coding", color: "#b69cff", radius: 3.55, speed: 0.16 },
    { id: "memory", color: "#ffd166", radius: 3.25, speed: 0.13 },
    { id: "planner", color: "#ff7ab6", radius: 3.65, speed: 0.11 },
];

function Core({ status }) {
    const ref = useRef();

    useFrame(({ clock }) => {
        const t = clock.getElapsedTime();

        const breathe = 1 + Math.sin(t * 1.7) * 0.055;
        const wobbleX = 1 + Math.sin(t * 2.1) * 0.025;
        const wobbleY = 1 + Math.cos(t * 1.8) * 0.035;
        const wobbleZ = 1 + Math.sin(t * 2.4) * 0.025;

        ref.current.scale.set(
            breathe * wobbleX,
            breathe * wobbleY,
            breathe * wobbleZ
        );

        ref.current.rotation.y += 0.003;
        ref.current.rotation.x = Math.sin(t * 0.35) * 0.12;
    });

    const color =
        status === "tool_started" ? "#6fffc4" :
            status === "tool_finished" ? "#aaffdd" :
                status === "agent_selected" ? "#b69cff" :
                    status === "speech_recognized" ? "#7cecff" :
                        status === "wake_detected" ? "#ffffff" :
                            status === "session_started" ? "#7cecff" :
                                status === "error" ? "#ff6b8a" :
                                    "#9df4ff";

    return (
        <mesh ref={ref}>
            <sphereGeometry args={[1.22, 128, 128]} />
            <meshPhysicalMaterial
                color={color}
                emissive={color}
                emissiveIntensity={1.8}
                roughness={0.08}
                metalness={0.05}
                transmission={0.35}
                thickness={1.2}
                clearcoat={1}
                clearcoatRoughness={0.08}
            />
        </mesh>
    );
}

function AgentNode({ agent, index, activeAgent }) {
    const ref = useRef();
    const labelRef = useRef();

    const angle = (index / AGENTS.length) * Math.PI * 2;
    const isActive = activeAgent === agent.id;

    useFrame(({ clock, camera }) => {
        const t = clock.getElapsedTime() * agent.speed + angle;

        ref.current.position.x = Math.cos(t) * agent.radius;
        ref.current.position.z = Math.sin(t) * agent.radius;
        ref.current.position.y = Math.sin(t * 1.5) * 0.35;

        if (labelRef.current) {
            labelRef.current.position.copy(ref.current.position);
            labelRef.current.position.y += 0.45;
            labelRef.current.lookAt(camera.position);
        }
    });

    return (
        <>
            <group ref={ref}>
                <mesh>
                    <sphereGeometry args={[isActive ? 0.3 : 0.18, 40, 40]} />
                    <meshStandardMaterial
                        color={isActive ? "#ffffff" : agent.color}
                        emissive={isActive ? "#ffffff" : agent.color}
                        emissiveIntensity={isActive ? 3.5 : 1.4}
                    />
                </mesh>
            </group>

            <Text
                ref={labelRef}
                fontSize={0.16}
                color={isActive ? "#ffffff" : agent.color}
                anchorX="center"
                anchorY="middle"
            >
                {agent.id.toUpperCase()}
            </Text>
        </>
    );
}

function EnergyBeam({ activeAgent }) {
    const beamRef = useRef();

    const agentIndex = AGENTS.findIndex((agent) => agent.id === activeAgent);
    const agent = agentIndex >= 0 ? AGENTS[agentIndex] : null;
    const angle = agent ? (agentIndex / AGENTS.length) * Math.PI * 2 : 0;

    const points = useMemo(() => {
        if (!agent) return [];

        const x = Math.cos(angle) * agent.radius;
        const z = Math.sin(angle) * agent.radius;

        return [
            new THREE.Vector3(0, 0, 0),
            new THREE.Vector3(x * 0.35, 0.45, z * 0.35),
            new THREE.Vector3(x * 0.7, -0.2, z * 0.7),
            new THREE.Vector3(x, 0, z),
        ];
    }, [agent, angle]);

    useFrame(({ clock }) => {
        if (beamRef.current) {
            beamRef.current.material.opacity =
                0.35 + Math.sin(clock.getElapsedTime() * 8) * 0.35;
        }
    });

    if (!agent || points.length === 0) return null;

    return (
        <Line
            ref={beamRef}
            points={points}
            color={agent.color}
            lineWidth={5}
            transparent
            opacity={0.85}
        />
    );
}

function MemoryDust() {
    const group = useRef();

    const particles = useMemo(() => {
        return Array.from({ length: 90 }, (_, i) => {
            const angle = Math.random() * Math.PI * 2;
            const radius = 1.8 + Math.random() * 2.2;
            return {
                id: i,
                x: Math.cos(angle) * radius,
                y: (Math.random() - 0.5) * 2.2,
                z: Math.sin(angle) * radius,
                size: Math.random() * 0.035 + 0.015,
            };
        });
    }, []);

    useFrame(({ clock }) => {
        group.current.rotation.y = clock.getElapsedTime() * 0.08;
    });

    return (
        <group ref={group}>
            {particles.map((p) => (
                <mesh key={p.id} position={[p.x, p.y, p.z]}>
                    <sphereGeometry args={[p.size, 12, 12]} />
                    <meshStandardMaterial
                        color="#bdf7ff"
                        emissive="#6be5ff"
                        emissiveIntensity={1.4}
                    />
                </mesh>
            ))}
        </group>
    );
}

function CoreRipples({ status }) {
    const rippleRef = useRef();

    useFrame(({ clock }) => {
        if (!rippleRef.current) return;

        const t = clock.getElapsedTime();
        rippleRef.current.rotation.z += 0.003;
        rippleRef.current.scale.setScalar(1 + Math.sin(t * 2.8) * 0.08);
    });

    const color =
        status === "tool_started" ? "#00ff99" :
            status === "agent_selected" ? "#9b7cff" :
                status === "speech_recognized" ? "#6be5ff" :
                    "#8df1ff";

    return (
        <group ref={rippleRef}>
            {[1.65, 2.05, 2.45].map((radius, index) => (
                <mesh key={index}>
                    <torusGeometry args={[radius, 0.01, 16, 160]} />
                    <meshStandardMaterial
                        color={color}
                        emissive={color}
                        emissiveIntensity={1.8 - index * 0.35}
                        transparent
                        opacity={0.45 - index * 0.1}
                    />
                </mesh>
            ))}
        </group>
    );
}

function NeuralSparks() {
    const groupRef = useRef();

    const sparks = useMemo(() => {
        return Array.from({ length: 14 }, (_, i) => {
            const a1 = Math.random() * Math.PI * 2;
            const a2 = a1 + (Math.random() - 0.5) * 1.4;

            const r1 = 1.8 + Math.random() * 1.7;
            const r2 = 1.8 + Math.random() * 1.7;

            return {
                id: i,
                start: new THREE.Vector3(
                    Math.cos(a1) * r1,
                    (Math.random() - 0.5) * 1.4,
                    Math.sin(a1) * r1
                ),
                end: new THREE.Vector3(
                    Math.cos(a2) * r2,
                    (Math.random() - 0.5) * 1.4,
                    Math.sin(a2) * r2
                ),
                delay: Math.random() * 2,
            };
        });
    }, []);

    useFrame(({ clock }) => {
        if (!groupRef.current) return;

        const t = clock.getElapsedTime();

        groupRef.current.children.forEach((child, index) => {
            const spark = sparks[index];
            const pulse = Math.sin((t + spark.delay) * 4);

            child.material.opacity = pulse > 0.65 ? 0.75 : 0.05;
        });
    });

    return (
        <group ref={groupRef}>
            {sparks.map((spark) => (
                <Line
                    key={spark.id}
                    points={[spark.start, spark.end]}
                    color="#d8fbff"
                    lineWidth={1.4}
                    transparent
                    opacity={0.08}
                />
            ))}
        </group>
    );
}
function EnergyParticles({ activeAgent }) {
    const groupRef = useRef();

    const agentIndex = AGENTS.findIndex((agent) => agent.id === activeAgent);
    const agent = agentIndex >= 0 ? AGENTS[agentIndex] : null;
    const angle = agent ? (agentIndex / AGENTS.length) * Math.PI * 2 : 0;

    const particles = useMemo(() => {
        return Array.from({ length: 18 }, (_, i) => ({
            id: i,
            offset: i / 18,
        }));
    }, []);

    useFrame(({ clock }) => {
        if (!groupRef.current || !agent) return;

        const t = clock.getElapsedTime();
        const endX = Math.cos(angle) * agent.radius;
        const endZ = Math.sin(angle) * agent.radius;

        groupRef.current.children.forEach((child, i) => {
            const p = (t * 0.75 + particles[i].offset) % 1;

            child.position.x = endX * p;
            child.position.y = Math.sin(p * Math.PI) * 0.35;
            child.position.z = endZ * p;

            const scale = 0.04 + Math.sin(p * Math.PI) * 0.045;
            child.scale.setScalar(scale);
        });
    });

    if (!agent) return null;

    return (
        <group ref={groupRef}>
            {particles.map((p) => (
                <mesh key={p.id}>
                    <sphereGeometry args={[1, 12, 12]} />
                    <meshStandardMaterial
                        color="#ffffff"
                        emissive={agent.color}
                        emissiveIntensity={3}
                        transparent
                        opacity={0.9}
                    />
                </mesh>
            ))}
        </group>
    );
}
function CameraRig({ activeAgent }) {
    const agentIndex = AGENTS.indexOf(activeAgent);
    const angle = agentIndex >= 0 ? (agentIndex / AGENTS.length) * Math.PI * 2 : null;

    useFrame(({ camera }) => {
        if (angle === null) {
            camera.position.lerp(new THREE.Vector3(0, 2.2, 7), 0.035);
        } else {
            const targetX = Math.cos(angle) * 0.9;
            const targetZ = 7 + Math.sin(angle) * 0.45;
            camera.position.lerp(new THREE.Vector3(targetX, 2.2, targetZ), 0.035);
        }

        camera.lookAt(0, 0, 0);
    });

    return null;
}

function Scene({ status, activeAgent }) {
    return (
        <>
            <ambientLight intensity={0.35} />
            <pointLight position={[0, 4, 5]} intensity={2.8} color="#6be5ff" />
            <pointLight position={[4, -2, -2]} intensity={1.5} color="#9b7cff" />

            <Stars radius={90} depth={45} count={2200} factor={4} fade speed={1.2} />

            <MemoryDust />
            <Core status={status} />
            <EnergyBeam activeAgent={activeAgent} />
            <EnergyParticles activeAgent={activeAgent} />

            {AGENTS.map((agent, i) => (
                <AgentNode
                    key={agent.id}
                    agent={agent}
                    index={i}
                    activeAgent={activeAgent}
                />
            ))}

            <CameraRig activeAgent={activeAgent} />

            <OrbitControls
                enableZoom={false}
                enablePan={false}
                enableRotate={false}
            />
        </>
    );
}

export default function BabyThreeMind({ status, activeAgent }) {
    return (
        <div className="three-mind">
            <Canvas camera={{ position: [0, 2.0, 6.4], fov: 56 }}>
                <Scene status={status} activeAgent={activeAgent} />
            </Canvas>
        </div>
    );
}