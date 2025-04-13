require('dotenv').config();
const { Client, GatewayIntentBits, Events } = require('discord.js');

// Replace 'YOUR_BOT_TOKEN_HERE' with your actual bot token.
const client = new Client({ 
    intents: [
        GatewayIntentBits.Guilds, 
        GatewayIntentBits.GuildMembers, 
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.DirectMessages,
        GatewayIntentBits.GuildMessages,
    ],
    partials: ['MESSAGE', 'CHANNEL', 'REACTION'] // Required to receive DMs
});

client.on('guildMemberAdd', async member => {
    try {
        const dmChannel = await member.createDM();

        // Helper function to ask a question and await reply
        const askQuestion = async (question) => {
            await dmChannel.send(question);
            const filter = response => response.author.id === member.id;
            const collected = await dmChannel.awaitMessages({ filter, max: 1, time: 60000, errors: ['time'] });
            return collected.first().content;
        };

        const name = await askQuestion("Welcome! What's your name?");
        const email = await askQuestion("What's your denison email?");
        const classYear = await askQuestion("What's your class year?");

        // Check if the email ends with 'denison.edu'
        if (email.trim().toLowerCase().endsWith('@denison.edu')) {
            // Change the server nickname and assign role
            try {
                await member.setNickname(`${name} - ${classYear}`);
                // Find the role "Students/Alumni" in the guild
                const role = member.guild.roles.cache.find(role => role.name === "Students/Alumni");
                if (role) {
                    await member.roles.add(role);
                    await dmChannel.send(`Success! Your nickname has been changed to: ${name} - ${classYear} and you have been assigned the "Students/Alumni" role.`);
                } else {
                    await dmChannel.send("Nickname updated successfully but the role 'Students/Alumni' was not found.");
                }
            } catch (err) {
                console.error('Failed to change nickname or assign role:', err);
                await dmChannel.send("I couldn't change your nickname or assign your role. Please contact an admin.");
            }
        } else {
            await dmChannel.send("Sorry, your email does not meet the required domain.");
        }
    } catch (error) {
        console.error('Error handling guild member join:', error);
    }
});


client.on("messageCreate", message => {
    if (message.author.bot) return;
    if (!message.guild) return;
    if (message.channel.name !== 'intern-process' && message.channel.name !== 'new-grad-process') return;

    const pattern = /^!process\s+(\S+)\s+(apply|OA|1st round|2nd round|final|offer)$/i;
    const match = pattern.exec(message.content);
    if (match) {
        message.react('✅').catch(console.error);
        if (match[2].toLowerCase() === 'offer') {
            message.channel.send(`Congrats 💐!`).catch(console.error);
        }
    } else {
        message.delete().catch(console.error);
        message.channel.send(`<@${message.author.id}>, please follow the format: "!process {company name} {apply|OA|1st round|2nd round|final|offer}"`)
            .then(notice => {
                setTimeout(() => {
                    notice.delete().catch(console.error);
                }, 10000);
            });
    }
});



// Log the bot in
client.login(process.env.DISCORD_TOKEN);